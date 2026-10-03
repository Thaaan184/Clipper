"""
Subtitle service — word-level timestamps → .ass kinetic subtitles.
Styled like Hormozi/TikTok: big bold centered, active word highlighted orange.
"""
import asyncio
import logging
from pathlib import Path
from faster_whisper import WhisperModel
from config import settings

logger = logging.getLogger(__name__)

# ASS header — Cutting Room style: flat black bg, white text, orange highlight
ASS_HEADER = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Fira Sans,72,&H00F5F5F5,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,0,2,80,80,120,1
Style: Highlight,Fira Sans,72,&H0000A8FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,0,2,80,80,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# &H0000A8FF = #FF6A00 in ASS BGR format


def _ts(seconds: float) -> str:
    """Convert float seconds to ASS timestamp H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass_from_segments(segments: list[dict], clip_start_offset: float = 0.0) -> str:
    """
    Build .ass subtitle content from faster-whisper segments.
    segments: list of {text, start, duration, words?: [{word, start, end}]}
    clip_start_offset: subtract this from all timestamps (clips start mid-video)
    """
    events = []

    for seg in segments:
        seg_start = seg["start"] - clip_start_offset
        seg_end = seg_start + seg.get("duration", 3.0)

        if seg_start < 0:
            continue

        text = seg.get("text", "").strip()
        if not text:
            continue

        words = seg.get("words", [])

        if words and len(words) > 1:
            # Word-by-word highlight: whole line visible, active word orange
            for i, word_obj in enumerate(words):
                w_start = word_obj["start"] - clip_start_offset
                w_end = word_obj["end"] - clip_start_offset

                if w_start < 0:
                    continue

                # Build line: non-active words normal, active word orange
                line_parts = []
                for j, w in enumerate(words):
                    w_text = w["word"].strip()
                    if j == i:
                        line_parts.append(f"{{\\c&H0000A8FF&}}{w_text}{{\\c&H00F5F5F5&}}")
                    else:
                        line_parts.append(w_text)

                line_text = " ".join(line_parts)
                events.append(f"Dialogue: 0,{_ts(w_start)},{_ts(w_end)},Default,,0,0,0,,{line_text}")
        else:
            # No word timestamps — show full segment
            events.append(f"Dialogue: 0,{_ts(seg_start)},{_ts(seg_end)},Default,,0,0,0,,{text}")

    return ASS_HEADER + "\n".join(events) + "\n"


async def generate_subtitle(
    audio_path: Path,
    output_path: Path,
    clip_start_offset: float = 0.0,
    lang: str = "id",
) -> bool:
    """
    Transcribe audio clip with faster-whisper word-level timestamps,
    generate .ass subtitle file.
    """
    try:
        model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type="int8",
            cpu_threads=4,
            local_files_only=True,
        )

        loop = asyncio.get_event_loop()

        def _transcribe():
            segments_gen, _ = model.transcribe(
                str(audio_path),
                language=lang,
                word_timestamps=True,
                vad_filter=True,
                hallucination_silence_threshold=2.0,
            )
            result = []
            for seg in segments_gen:
                entry = {
                    "text": seg.text.strip(),
                    "start": seg.start,
                    "duration": seg.end - seg.start,
                    "words": [],
                }
                if seg.words:
                    entry["words"] = [{"word": w.word, "start": w.start, "end": w.end} for w in seg.words]
                result.append(entry)
            return result

        segments = await loop.run_in_executor(None, _transcribe)

        if not segments:
            logger.warning("No segments from whisper for %s", audio_path.name)
            return False

        ass_content = build_ass_from_segments(segments, clip_start_offset)
        output_path.write_text(ass_content, encoding="utf-8")
        logger.info("Subtitle written: %s (%d events)", output_path.name, len(segments))
        return True

    except Exception as e:
        logger.error("Subtitle generation failed: %s", e)
        return False

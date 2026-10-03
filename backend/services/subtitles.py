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

# ASS header — TikTok/Reels viral motion subtitle style
ASS_HEADER = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,76,&H00F5F5F5,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,6,2,2,60,60,220,1

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
    Build .ass kinetic/motion subtitle content with chunked 3-4 word displays,
    active word pop scale (112%) and orange (#FF6A00) highlight.
    """
    events = []
    CHUNK_SIZE = 4

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
            # Chunk words into groups of 3-4 words for fast mobile readability
            word_chunks = [words[k:k + CHUNK_SIZE] for k in range(0, len(words), CHUNK_SIZE)]

            for chunk in word_chunks:
                if not chunk:
                    continue
                for i, word_obj in enumerate(chunk):
                    w_start = word_obj["start"] - clip_start_offset
                    w_end = word_obj["end"] - clip_start_offset

                    if w_start < 0:
                        continue

                    line_parts = []
                    for j, w in enumerate(chunk):
                        w_text = w["word"].strip().upper()
                        if j == i:
                            # Active word: pop 112% size + solid orange #FF6A00
                            line_parts.append(f"{{\\fscx112\\fscy112\\c&H0000A8FF&}}{w_text}{{\\fscx100\\fscy100\\c&H00F5F5F5&}}")
                        else:
                            line_parts.append(w_text)

                    line_text = " ".join(line_parts)
                    events.append(f"Dialogue: 0,{_ts(w_start)},{_ts(w_end)},Default,,0,0,0,,{line_text}")
        else:
            # Fallback when word timestamps are unavailable
            events.append(f"Dialogue: 0,{_ts(seg_start)},{_ts(seg_end)},Default,,0,0,0,,{text.upper()}")

    return ASS_HEADER + "\n".join(events) + "\n"


def build_ass_from_cues(cues: list[dict], clip_start_offset: float = 0.0) -> str:
    """
    Build .ass kinetic subtitles from a list of user-provided or stored cues.
    Each cue: {"start": float, "end": float, "text": str, "words": optional list}
    If word timestamps are missing, words are interpolated evenly across duration.
    """
    segments = []
    for c in cues:
        start = float(c.get("start", 0.0))
        end = float(c.get("end", start + 3.0))
        text = str(c.get("text", "")).strip()
        if not text:
            continue
        words = c.get("words", [])
        if not words:
            word_tokens = text.split()
            if word_tokens:
                dur = max(0.2, end - start)
                w_step = dur / len(word_tokens)
                words = [
                    {
                        "word": w,
                        "start": round(start + i * w_step, 3),
                        "end": round(start + (i + 1) * w_step, 3),
                    }
                    for i, w in enumerate(word_tokens)
                ]
        segments.append({
            "start": start,
            "duration": max(0.1, end - start),
            "text": text,
            "words": words,
        })
    return build_ass_from_segments(segments, clip_start_offset)


async def generate_subtitle(
    audio_path: Path,
    output_path: Path,
    clip_start_offset: float = 0.0,
    lang: str = "id",
) -> tuple[bool, list[dict]]:
    """
    Transcribe audio clip with faster-whisper word-level timestamps,
    generate .ass subtitle file and return segments data.
    """
    try:
        model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type="int8",
            cpu_threads=4,
            download_root=str(settings.data_dir / "models"),
            local_files_only=False,
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
            return False, []

        ass_content = build_ass_from_segments(segments, clip_start_offset)
        output_path.write_text(ass_content, encoding="utf-8")
        logger.info("Subtitle written: %s (%d events)", output_path.name, len(segments))
        return True, segments

    except Exception as e:
        logger.error("Subtitle generation failed: %s", e)
        return False, []

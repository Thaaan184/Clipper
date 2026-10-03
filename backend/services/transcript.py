"""
Transcript service — yt-dlp auto-subs first, youtube-transcript-api second, faster-whisper fallback.
"""
import asyncio
import logging
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from config import settings

logger = logging.getLogger(__name__)


def _extract_video_id(url: str) -> str:
    """Extract YouTube video ID from any URL format."""
    patterns = [
        r"youtube\.com/watch\?v=([\w\-]{11})",
        r"youtu\.be/([\w\-]{11})",
        r"youtube\.com/live/([\w\-]{11})",
        r"youtube\.com/shorts/([\w\-]{11})",
        r"youtube\.com/embed/([\w\-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    raise ValueError(f"Cannot extract video ID from: {url}")


def _parse_vtt(vtt_text: str) -> list[dict]:
    """Parse WebVTT content into list of {start, duration, text} dicts."""
    pattern = re.compile(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})")
    entries = []
    lines = vtt_text.splitlines()
    i = 0
    last_text = ""
    while i < len(lines):
        m = pattern.search(lines[i])
        if m:
            h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, m.groups())
            start = round(h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0, 3)
            end = round(h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0, 3)
            i += 1
            text_parts = []
            while i < len(lines) and lines[i].strip() and not pattern.search(lines[i]):
                clean = re.sub(r"<[^>]+>", "", lines[i]).strip()
                if clean and clean not in text_parts:
                    text_parts.append(clean)
                i += 1
            raw_text = " ".join(text_parts).strip()
            if raw_text and raw_text != last_text and (end - start) > 0.15:
                entries.append({"start": start, "duration": round(end - start, 3), "text": raw_text})
                last_text = raw_text
        else:
            i += 1
    return entries


async def get_transcript_from_ytdlp(url: str, lang: str = "id") -> list[dict]:
    """Download captions via yt-dlp (bypasses transcript-api blocks, works with auto-subs)."""
    loop = asyncio.get_event_loop()

    def _extract():
        with tempfile.TemporaryDirectory() as tmpdir:
            out_tmpl = str(Path(tmpdir) / "sub.%(ext)s")
            ytdlp_bin = shutil.which("yt-dlp") or str(Path(sys.executable).parent / "yt-dlp") or "yt-dlp"
            cmd = [
                ytdlp_bin,
                "--write-auto-subs",
                "--write-subs",
                "--sub-lang", f"{lang},en",
                "--skip-download",
                "--sub-format", "vtt",
                "--extractor-args", "youtube:player_client=android,web",
                "-o", out_tmpl,
                url,
            ]
            subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            vtt_files = list(Path(tmpdir).glob("*.vtt"))
            if not vtt_files:
                return []
            target_vtt = None
            for vf in vtt_files:
                if f".{lang}." in vf.name:
                    target_vtt = vf
                    break
            if not target_vtt:
                target_vtt = vtt_files[0]

            with open(target_vtt, "r", encoding="utf-8", errors="ignore") as f:
                return _parse_vtt(f.read())

    try:
        return await loop.run_in_executor(None, _extract)
    except Exception as e:
        logger.warning("yt-dlp subtitle download failed: %s", e)
        return []


async def get_transcript_from_api(video_id: str, lang: str = "id") -> list[dict]:
    """Fetch transcript via youtube-transcript-api (fast, no download)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        loop = asyncio.get_event_loop()
        try:
            transcript = await loop.run_in_executor(
                None,
                lambda: YouTubeTranscriptApi.get_transcript(video_id, languages=[lang, "en", "id"]),
            )
        except Exception:
            transcript = await loop.run_in_executor(
                None,
                lambda: YouTubeTranscriptApi.get_transcript(video_id),
            )
        return transcript  # [{text, start, duration}]
    except Exception as e:
        logger.warning("youtube-transcript-api failed: %s", e)
        return []


async def transcribe_with_whisper(audio_path: Path, lang: str = "id") -> list[dict]:
    """Transcribe audio file via faster-whisper, get timestamps."""
    try:
        from faster_whisper import WhisperModel

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
            segments_gen, info = model.transcribe(
                str(audio_path),
                language=lang,
                word_timestamps=False,
                vad_filter=False,
                beam_size=1,
            )
            result = []
            for seg in segments_gen:
                result.append({
                    "text": seg.text.strip(),
                    "start": round(seg.start, 2),
                    "duration": round(seg.end - seg.start, 2),
                })
            return result

        return await loop.run_in_executor(None, _transcribe)
    except Exception as e:
        logger.error("faster-whisper transcription failed: %s", e)
        return []


def format_transcript_for_llm(transcript: list[dict]) -> str:
    """Format transcript list to timestamped text for LLM."""
    lines = []
    for entry in transcript:
        start = entry.get("start", 0)
        text = entry.get("text", "").strip()
        if text:
            minutes = int(start // 60)
            seconds = start % 60
            lines.append(f"[{minutes:02d}:{seconds:05.2f}] {text}")
    return "\n".join(lines)


async def get_transcript(
    video_id: str,
    lang: str = "id",
    audio_path: Path | None = None,
    url: str | None = None,
) -> tuple[list[dict], str]:
    """
    Get transcript with 3-tier fallback chain:
    1. yt-dlp auto-captions / manual subs
    2. youtube-transcript-api
    3. faster-whisper local audio transcription
    Returns (transcript_list, source) where source is 'yt-dlp' | 'api' | 'whisper' | 'empty'
    """
    # 1. Try yt-dlp first if URL given
    if url:
        transcript = await get_transcript_from_ytdlp(url, lang)
        if transcript:
            logger.info("Transcript from yt-dlp: %d segments", len(transcript))
            return transcript, "yt-dlp"

    # 2. Try youtube-transcript-api
    transcript = await get_transcript_from_api(video_id, lang)
    if transcript:
        logger.info("Transcript from API: %d segments", len(transcript))
        return transcript, "api"

    # 3. Fallback to whisper if audio available
    if audio_path and audio_path.exists():
        logger.info("Falling back to faster-whisper for %s", audio_path)
        transcript = await transcribe_with_whisper(audio_path, lang)
        if transcript:
            return transcript, "whisper"

    logger.warning("No transcript available for %s", video_id)
    return [], "empty"

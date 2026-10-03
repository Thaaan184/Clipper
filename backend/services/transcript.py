"""
Transcript service — youtube-transcript-api first, faster-whisper fallback.
"""
import asyncio
import logging
import re
from pathlib import Path
from config import settings

logger = logging.getLogger(__name__)


def _extract_video_id(url: str) -> str:
    """Extract YouTube video ID from any URL format."""
    patterns = [
        r"youtube\.com/watch\?v=([\w\-]{11})",
        r"youtu\.be/([\w\-]{11})",
        r"youtube\.com/shorts/([\w\-]{11})",
        r"youtube\.com/embed/([\w\-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    raise ValueError(f"Cannot extract video ID from: {url}")


async def get_transcript_from_api(video_id: str, lang: str = "id") -> list[dict]:
    """Fetch transcript via youtube-transcript-api (fast, no download)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        loop = asyncio.get_event_loop()
        # Try requested language first, then fallback to any
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
    """Transcribe audio file via faster-whisper, get word-level timestamps."""
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type="int8",
        )

        loop = asyncio.get_event_loop()

        def _transcribe():
            segments_gen, info = model.transcribe(
                str(audio_path),
                language=lang,
                word_timestamps=True,
                vad_filter=True,
                hallucination_silence_threshold=2.0,
            )
            result = []
            for seg in segments_gen:
                result.append({
                    "text": seg.text.strip(),
                    "start": seg.start,
                    "duration": seg.end - seg.start,
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


async def get_transcript(video_id: str, lang: str = "id", audio_path: Path | None = None) -> tuple[list[dict], str]:
    """
    Get transcript with fallback chain.
    Returns (transcript_list, source) where source is 'api' | 'whisper' | 'empty'
    """
    # Try API first (no download needed)
    transcript = await get_transcript_from_api(video_id, lang)
    if transcript:
        logger.info("Transcript from API: %d segments", len(transcript))
        return transcript, "api"

    # Fallback to whisper if audio available
    if audio_path and audio_path.exists():
        logger.info("Falling back to faster-whisper for %s", audio_path)
        transcript = await transcribe_with_whisper(audio_path, lang)
        if transcript:
            return transcript, "whisper"

    logger.warning("No transcript available for %s", video_id)
    return [], "empty"

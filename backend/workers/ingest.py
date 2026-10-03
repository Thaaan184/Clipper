"""
Ingest worker — Phase 1.
Fetches YouTube metadata + transcript + audio spikes.
Updates job progress via SSE event queue.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime

import aiosqlite
import yt_dlp

from config import settings
from services.transcript import get_transcript, format_transcript_for_llm, _extract_video_id
from workers.audio_analysis import download_audio, detect_energy_spikes

logger = logging.getLogger(__name__)


async def _update_job(db_path: str, job_id: str, **kwargs):
    async with aiosqlite.connect(db_path) as db:
        fields = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [datetime.utcnow().isoformat(), job_id]
        await db.execute(f"UPDATE jobs SET {fields}, updated_at = ? WHERE id = ?", values)
        await db.commit()


async def _update_video(db_path: str, video_id: str, **kwargs):
    async with aiosqlite.connect(db_path) as db:
        fields = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [datetime.utcnow().isoformat(), video_id]
        await db.execute(f"UPDATE videos SET {fields}, updated_at = ? WHERE id = ?", values)
        await db.commit()


def _ydl_extract_info(url: str, ydl_opts: dict) -> dict:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


async def run_ingest(
    job_id: str,
    video_id: str,
    url: str,
    subtitle_lang: str,
    progress_queue: asyncio.Queue,
    db_path: str,
):
    """
    Phase 1: Ingest metadata + transcript + audio spikes.
    Sends progress events to progress_queue.
    """

    async def emit(phase: str, progress: int, message: str):
        await progress_queue.put({
            "event": "progress",
            "job_id": job_id,
            "phase": phase,
            "progress": progress,
            "message": message,
        })
        await _update_job(db_path, job_id, phase=phase, progress=progress, message=message, status="running")

    try:
        await emit("ingest", 5, "Mengambil metadata video...")

        # Step 1: yt-dlp metadata (no download)
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
        }

        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, _ydl_extract_info, url, ydl_opts)

        title = info.get("title", "Untitled")
        duration = int(info.get("duration", 0))
        thumbnail = info.get("thumbnail", "")
        channel = info.get("uploader", "")

        if duration > settings.max_video_duration:
            raise ValueError(f"Video terlalu panjang: {duration//3600}j {(duration%3600)//60}m (maks {settings.max_video_duration//3600}j)")

        await _update_video(db_path, video_id, title=title, duration=duration, thumbnail=thumbnail, channel=channel)
        await emit("ingest", 20, f"Metadata OK: \"{title}\" ({duration//60}m {duration%60}s)")

        # Step 2: Get transcript
        await emit("ingest", 30, "Mengambil transkrip...")
        yt_video_id = _extract_video_id(url)
        transcript, source = await get_transcript(yt_video_id, subtitle_lang, url=url)

        audio_path = None
        if not transcript:
            # Livestream just ended, or video has disabled captions
            if duration <= 1800:
                await emit("ingest", 35, "Tidak ada CC — download audio untuk transkripsi Whisper...")
                audio_path = await download_audio(url, video_id)
                if audio_path:
                    transcript, source = await get_transcript(yt_video_id, subtitle_lang, audio_path=audio_path)
            else:
                logger.info("Video %s panjang (%ds) tanpa CC. Memakai mode Instant Highlight Scout.", video_id, duration)
                await emit("ingest", 35, "CC belum tersedia (live baru selesai). Memindai highlight momen...")
                source = "live_highlight"

        transcript_text = format_transcript_for_llm(transcript) if transcript else ""
        await _update_video(db_path, video_id, transcript=transcript_text)
        if transcript:
            await emit("ingest", 55, f"Transkrip OK via {source}: {len(transcript)} segmen")
        else:
            await emit("ingest", 55, "Mode live stream: siap scouting highlight momen")

        # Step 3: Audio spike detection
        await emit("ingest", 60, "Analisis energi audio...")
        spikes = []
        if audio_path is None and duration <= 3600:
            try:
                audio_path = await download_audio(url, video_id)
            except Exception as e:
                logger.warning("Download audio for spikes failed: %s", e)

        if audio_path and audio_path.exists():
            try:
                spikes = await detect_energy_spikes(audio_path)
            except Exception as e:
                logger.warning("Spike detection error: %s", e)

        spikes_json = json.dumps(spikes)
        await _update_video(db_path, video_id, audio_spikes=spikes_json)
        await emit("ingest", 80, f"Audio analisis OK: {len(spikes)} spike terdeteksi")

        await _update_video(db_path, video_id, status="ingested")
        await _update_job(db_path, job_id, status="done", progress=100, phase="ingest", message="Ingest selesai")
        await emit("ingest", 100, "Ingest selesai")

        return {
            "title": title,
            "duration": duration,
            "transcript_text": transcript_text,
            "spikes": spikes,
        }

    except Exception as e:
        err = str(e)
        logger.error("Ingest failed for %s: %s", video_id, err)
        await _update_video(db_path, video_id, status="error", error_msg=err)
        await _update_job(db_path, job_id, status="error", error_msg=err)
        await progress_queue.put({
            "event": "error",
            "job_id": job_id,
            "error": err,
        })
        raise

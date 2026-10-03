"""
Scout worker — Phase 2.
Calls LLM to find and score best moments, writes clip records to DB.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime

import aiosqlite

from config import settings
from services.llm import scout_moments

logger = logging.getLogger(__name__)


async def _update_job(db_path: str, job_id: str, **kwargs):
    async with aiosqlite.connect(db_path) as db:
        fields = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [datetime.utcnow().isoformat(), job_id]
        await db.execute(f"UPDATE jobs SET {fields}, updated_at = ? WHERE id = ?", values)
        await db.commit()


async def run_scout(
    job_id: str,
    video_id: str,
    transcript_text: str,
    audio_spikes: list[dict],
    video_duration: int,
    clip_count: int,
    duration_target: str,
    subtitle_lang: str,
    layout: str,
    progress_queue: asyncio.Queue,
    db_path: str,
) -> list[str]:
    """
    Phase 2: Scout moments via LLM, write clip records.
    Returns list of clip IDs created.
    """

    async def emit(progress: int, message: str):
        await progress_queue.put({
            "event": "progress",
            "job_id": job_id,
            "phase": "scout",
            "progress": progress,
            "message": message,
        })
        await _update_job(db_path, job_id, phase="scout", progress=progress, message=message, status="running")

    try:
        await emit(5, "AI sedang menganalisis transkrip...")

        moments = await scout_moments(
            transcript_text=transcript_text,
            audio_spikes=audio_spikes,
            duration_target=duration_target,
            clip_count=clip_count,
            video_duration=video_duration,
        )

        if not moments:
            raise ValueError("AI tidak menemukan momen yang layak di video ini")

        await emit(80, f"Ditemukan {len(moments)} momen terbaik")

        # Write clip records to DB
        clip_ids = []
        async with aiosqlite.connect(db_path) as db:
            for i, m in enumerate(moments):
                clip_id = str(uuid.uuid4())
                dur = round(m["end_time"] - m["start_time"], 3)
                hashtags_json = json.dumps(m.get("hashtags", []))

                await db.execute(
                    """INSERT INTO clips
                    (id, video_id, clip_index, start_time, end_time, duration,
                     hook_title, score, reason, caption, hashtags, content_type,
                     layout, subtitle_lang, status, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        clip_id, video_id, i + 1,
                        m["start_time"], m["end_time"], dur,
                        m.get("hook_title", f"Klip {i+1}"),
                        m.get("score", 50),
                        m.get("reason", ""),
                        m.get("caption", ""),
                        hashtags_json,
                        m.get("content_type", "general"),
                        layout,
                        subtitle_lang,
                        "pending",
                        datetime.utcnow().isoformat(),
                        datetime.utcnow().isoformat(),
                    ),
                )
                clip_ids.append(clip_id)
            await db.commit()

        await emit(100, f"{len(clip_ids)} klip siap dirender")
        await _update_job(db_path, job_id, status="done", progress=100, phase="scout")
        return clip_ids

    except Exception as e:
        err = str(e)
        logger.error("Scout failed for %s: %s", video_id, err)
        await _update_job(db_path, job_id, status="error", error_msg=err)
        await progress_queue.put({"event": "error", "job_id": job_id, "error": err})
        raise

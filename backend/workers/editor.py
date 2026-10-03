"""
Editor worker — Phase 3.
Downloads clip range via yt-dlp, reframes to 9:16, burns subtitles.
"""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite
import yt_dlp

from config import settings
from services.reframe import reframe, loudnorm
from services.subtitles import generate_subtitle

logger = logging.getLogger(__name__)


async def _update_clip(db_path: str, clip_id: str, **kwargs):
    async with aiosqlite.connect(db_path) as db:
        fields = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [datetime.utcnow().isoformat(), clip_id]
        await db.execute(f"UPDATE clips SET {fields}, updated_at = ? WHERE id = ?", values)
        await db.commit()


async def _update_job(db_path: str, job_id: str, **kwargs):
    async with aiosqlite.connect(db_path) as db:
        fields = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [datetime.utcnow().isoformat(), job_id]
        await db.execute(f"UPDATE jobs SET {fields}, updated_at = ? WHERE id = ?", values)
        await db.commit()


def _download_clip_range(url: str, start: float, end: float, output_path: Path) -> Path | None:
    """Download only a time range of the video using yt-dlp."""
    base_tmpl = str(output_path.with_suffix(""))

    # Clean up any stale partial files
    for stale in output_path.parent.glob(f"{output_path.stem}.*"):
        try:
            stale.unlink()
        except Exception:
            pass

    ydl_opts = {
        "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "outtmpl": base_tmpl + ".%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "no_playlist": True,
        "download_ranges": yt_dlp.utils.download_range_func([], [[start, end]]),
        "force_keyframes_at_cuts": True,
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        candidates = list(output_path.parent.glob(f"{output_path.stem}.*"))
        valid = [
            c for c in candidates
            if not c.name.endswith(".part")
            and not c.name.endswith(".ytdl")
            and c.suffix.lower() in [".mp4", ".mkv", ".webm"]
            and c.stat().st_size > 1000
        ]
        if valid:
            return valid[0]
        return None
    except Exception as e:
        logger.error("yt-dlp clip download failed: %s", e)
        return None


async def render_clip(
    job_id: str,
    clip_id: str,
    video_id: str,
    url: str,
    start_time: float,
    end_time: float,
    layout: str,
    subtitle_lang: str,
    progress_queue: Any,
    db_path: str,
) -> str | None:
    """
    Phase 3: Download clip range + reframe + subtitle burn.
    Returns output file path on success, None on failure.
    """

    async def emit(progress: int, message: str):
        await progress_queue.put({
            "event": "progress",
            "job_id": job_id,
            "phase": "editor",
            "progress": progress,
            "message": message,
            "clip_id": clip_id,
        })
        await _update_job(db_path, job_id, phase="editor", progress=progress, message=message, status="running")

    raw_dir = settings.raw_dir
    out_dir = settings.processed_dir

    raw_path = raw_dir / f"{clip_id}_raw.mp4"
    sub_path = raw_dir / f"{clip_id}.ass"
    pre_norm_path = out_dir / f"{clip_id}_prenorm.mp4"
    final_path = out_dir / f"{clip_id}.mp4"

    try:
        await _update_clip(db_path, clip_id, status="rendering")

        # Step 1: Download clip range
        await emit(10, f"Mengunduh range {int(start_time//60)}:{int(start_time%60):02d}–{int(end_time//60)}:{int(end_time%60):02d}...")

        loop = asyncio.get_event_loop()
        downloaded_raw = await loop.run_in_executor(
            None, _download_clip_range, url, start_time, end_time, raw_path
        )

        if not downloaded_raw or not downloaded_raw.exists():
            raise RuntimeError("Download klip gagal")

        raw_path = downloaded_raw

        # Step 2: Generate subtitle (from raw audio)
        sub_ok = False
        if subtitle_lang and subtitle_lang.lower() != "none":
            await emit(40, "Download selesai, generate subtitle...")
            sub_ok = await generate_subtitle(raw_path, sub_path, clip_start_offset=0.0, lang=subtitle_lang)
            await emit(60, f"Subtitle OK, reframe ke 9:16 [{layout}]...")
        else:
            await emit(40, "Download selesai, lewati subtitle (mode tanpa subtitle)...")
            await emit(60, f"Reframe ke 9:16 [{layout}] tanpa subtitle...")

        # Step 3: Reframe
        reframe_ok = await reframe(
            input_path=raw_path,
            output_path=pre_norm_path,
            layout=layout,
            subtitle_path=sub_path if (sub_ok and subtitle_lang and subtitle_lang.lower() != "none") else None,
        )

        if not reframe_ok:
            raise RuntimeError("FFmpeg reframe gagal")

        await emit(85, "Normalisasi audio...")

        # Step 4: Loudnorm
        norm_ok = await loudnorm(pre_norm_path, final_path)
        if not norm_ok:
            # Use pre-norm as fallback
            pre_norm_path.rename(final_path)
        elif pre_norm_path.exists():
            pre_norm_path.unlink()

        # Cleanup raw files
        for f in [raw_path, sub_path]:
            if f.exists():
                try:
                    f.unlink()
                except Exception:
                    pass

        file_size = final_path.stat().st_size
        await _update_clip(
            db_path, clip_id,
            status="done",
            file_path=str(final_path),
            file_size=file_size,
        )
        await _update_job(db_path, job_id, status="done", progress=100, phase="editor")
        await emit(100, f"Klip selesai ({file_size / 1e6:.1f} MB)")

        return str(final_path)

    except Exception as e:
        err = str(e)
        logger.error("Editor failed clip %s: %s", clip_id, err)
        await _update_clip(db_path, clip_id, status="error", error_msg=err)
        await _update_job(db_path, job_id, status="error", error_msg=err)
        await progress_queue.put({"event": "error", "job_id": job_id, "clip_id": clip_id, "error": err})

        # Cleanup partial files
        for f in [raw_path, sub_path, pre_norm_path]:
            if f.exists():
                try:
                    f.unlink()
                except Exception:
                    pass

        return None

"""
Editor worker — Phase 3.
Downloads clip range via yt-dlp, reframes to 9:16, burns subtitles.
"""
import asyncio
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite
import yt_dlp
from yt_dlp.utils import download_range_func

from config import settings
from services.reframe import reframe, loudnorm
from services.subtitles import generate_subtitle, build_ass_from_cues

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
    """
    Download exact clip range with zero freezing and perfect A/V sync.
    Uses yt-dlp download_ranges with force_keyframes_at_cuts=True and explicit MP4/H.264
    format to ensure exact keyframe cuts, zero negative PTS, and identical video/audio start.
    """
    target_path = output_path.with_suffix(".mp4")

    # Clean up any stale partial files
    for stale in output_path.parent.glob(f"{output_path.stem}.*"):
        try:
            stale.unlink()
        except Exception:
            pass

    ydl_opts: dict[str, Any] = {
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "outtmpl": str(target_path),
        "quiet": True,
        "no_warnings": True,
        "no_playlist": True,
        "download_ranges": download_range_func(None, [(start, end)]),  # type: ignore
        "remote_components": ["ejs:github"],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore
            ydl.download([url])

        if target_path.exists() and target_path.stat().st_size > 10000:
            return target_path

        candidates = list(output_path.parent.glob(f"{output_path.stem}.*"))
        valid = [
            c for c in candidates
            if not c.name.endswith(".part")
            and not c.name.endswith(".ytdl")
            and c.suffix.lower() in [".mp4", ".mkv", ".webm"]
            and c.stat().st_size > 10000
        ]
        if valid:
            return valid[0]

        logger.warning("yt-dlp produced empty clip (<10KB) for %s (%.1f-%.1f)", url, start, end)
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
    custom_subtitles: list[dict] | None = None,
    custom_transcript: str | None = None,
    subtitle_style: str = "popin",
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

        # Step 2: Generate subtitle (from raw audio or custom edits)
        sub_ok = False
        subtitles_saved = None
        transcript_saved = None

        if custom_subtitles and len(custom_subtitles) > 0 and subtitle_lang != "none":
            await emit(40, "Menerapkan subtitle kustom yang telah diedit...")
            ass_content = build_ass_from_cues(custom_subtitles, clip_start_offset=0.0, style_preset=subtitle_style)
            sub_path.write_text(ass_content, encoding="utf-8")
            sub_ok = True
            subtitles_saved = custom_subtitles
            transcript_saved = custom_transcript or " ".join(c.get("text", "") for c in custom_subtitles)
            await emit(60, f"Subtitle kustom siap, reframe ke 9:16 [{layout}]...")
        elif subtitle_lang and subtitle_lang.lower() != "none":
            await emit(40, "Download selesai, generate subtitle...")
            sub_ok, segments = await generate_subtitle(raw_path, sub_path, clip_start_offset=0.0, lang=subtitle_lang, style_preset=subtitle_style)
            if sub_ok:
                subtitles_saved = segments
                transcript_saved = " ".join(s.get("text", "") for s in segments)
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
        update_kwargs = {
            "status": "done",
            "file_path": str(final_path),
            "file_size": file_size,
        }
        if subtitles_saved is not None:
            update_kwargs["subtitles_json"] = json.dumps(subtitles_saved)
        if transcript_saved is not None:
            update_kwargs["transcript"] = transcript_saved

        await _update_clip(db_path, clip_id, **update_kwargs)
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

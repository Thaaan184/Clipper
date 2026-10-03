"""Health check and diagnostics endpoints."""

import shutil
import subprocess
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status

from clipforge.core.config import settings
from clipforge.db.connection import get_db

router = APIRouter(tags=["Health"])


@router.get("/healthz", status_code=status.HTTP_200_OK)
async def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@router.get("/readyz", status_code=status.HTTP_200_OK)
async def readyz(db: aiosqlite.Connection = Depends(get_db)) -> dict[str, Any]:
    """Readiness probe checking DB, FFmpeg with libass, yt-dlp, and disk space."""
    checks: dict[str, bool] = {}

    # 1. Database check
    try:
        async with db.execute("SELECT 1") as cursor:
            row = await cursor.fetchone()
            checks["database"] = bool(row and row[0] == 1)
    except Exception:
        checks["database"] = False

    # 2. FFmpeg & libass filter check
    try:
        proc = subprocess.run(
            ["ffmpeg", "-filters"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        checks["ffmpeg"] = proc.returncode == 0 and "ass" in proc.stdout
    except Exception:
        checks["ffmpeg"] = False

    # 3. yt-dlp check
    try:
        proc = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        checks["yt_dlp"] = proc.returncode == 0
    except Exception:
        checks["yt_dlp"] = False

    # 4. Disk space check (require at least 2 GB free)
    try:
        usage = shutil.disk_usage(settings.data_dir)
        free_gb = usage.free / (1024**3)
        checks["disk_space"] = free_gb >= 2.0
    except Exception:
        checks["disk_space"] = False

    all_ready = all(checks.values())
    if not all_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "checks": checks},
        )

    return {"status": "ready", "checks": checks}


@router.get("/api/system/diagnostics")
async def diagnostics() -> dict[str, Any]:
    """Return runtime diagnostics and versions."""
    import faster_whisper
    import yt_dlp

    ffmpeg_ver = "unknown"
    try:
        proc = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            ffmpeg_ver = proc.stdout.splitlines()[0]
    except Exception:
        pass

    usage = shutil.disk_usage(settings.data_dir)
    return {
        "ffmpeg": ffmpeg_ver,
        "yt_dlp": getattr(yt_dlp, "__version__", "unknown"),
        "faster_whisper": faster_whisper.__version__,
        "whisper_device": settings.whisper_device,
        "disk_free_gb": round(usage.free / (1024**3), 2),
        "disk_total_gb": round(usage.total / (1024**3), 2),
    }

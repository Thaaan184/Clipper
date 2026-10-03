"""Thumbnail extraction for rendered clips."""

import subprocess
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


def extract_thumbnail(
    video_path: Path,
    output_path: Path,
    time_s: float = 1.0,
    width: int = 540,
    height: int = 960,
) -> bool:
    """Extract a thumbnail frame from a video at time_s."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{max(0.0, time_s):.2f}",
        "-i",
        str(video_path),
        "-vf",
        f"scale={width}:{height}:flags=lanczos",
        "-frames:v",
        "1",
        "-loglevel",
        "error",
        str(output_path),
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        logger.warning(
            "thumbnail_extraction_failed",
            video=str(video_path),
            stderr=proc.stderr.decode("utf-8", errors="replace"),
        )
        return False
    return output_path.exists() and output_path.stat().st_size > 0

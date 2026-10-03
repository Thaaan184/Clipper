"""
Reframe service — FFmpeg 9:16 layouts.
All functions return the ffmpeg command list for subprocess.
"""
import subprocess
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _escape_filter_path(p: Path) -> str:
    """Escape path for FFmpeg filter argument (colons, backslashes, quotes)."""
    return str(p.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def _blur_bg_cmd(input_path: Path, output_path: Path, subtitle_path: Path | None = None) -> list[str]:
    """
    Layout: blur background fill, original centered.
    Safe for game content — full HUD/minimap visible.
    Optimized: downscales bg to 270x480 for 10x faster blur.
    """
    filters = (
        "[0:v]scale=270:480:force_original_aspect_ratio=increase,"
        "crop=270:480,boxblur=8:1,scale=1080:1920[bg];"
        "[0:v]scale=1080:-2[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
    )
    if subtitle_path and subtitle_path.exists():
        sub_esc = _escape_filter_path(subtitle_path)
        filters += f";[v]ass='{sub_esc}'[vout]"
        map_video = "[vout]"
    else:
        map_video = "[v]"

    return [
        "ffmpeg", "-y", "-i", str(input_path),
        "-filter_complex", filters,
        "-map", map_video, "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]


def _center_crop_cmd(input_path: Path, output_path: Path, subtitle_path: Path | None = None) -> list[str]:
    """
    Layout: center crop to 9:16.
    Best for FPS games — focuses on crosshair area.
    """
    filters = "[0:v]crop=ih*9/16:ih,scale=1080:1920[v]"
    if subtitle_path and subtitle_path.exists():
        sub_esc = _escape_filter_path(subtitle_path)
        filters += f";[v]ass='{sub_esc}'[vout]"
        map_video = "[vout]"
    else:
        map_video = "[v]"

    return [
        "ffmpeg", "-y", "-i", str(input_path),
        "-filter_complex", filters,
        "-map", map_video, "-map", "0:a?",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]


def _stacked_cmd(input_path: Path, output_path: Path, subtitle_path: Path | None = None) -> list[str]:
    """
    Layout: top = webcam area (top-left 25%), bottom = gameplay center.
    Best for streamers with facecam overlay.
    """
    filters = (
        "[0:v]crop=iw*0.3:ih*0.3:0:0,scale=1080:720[cam];"
        "[0:v]crop=iw*0.7:ih*0.7:iw*0.15:ih*0.15,scale=1080:1200[game];"
        "[cam][game]vstack[v]"
    )
    if subtitle_path and subtitle_path.exists():
        sub_esc = _escape_filter_path(subtitle_path)
        filters += f";[v]ass='{sub_esc}'[vout]"
        map_video = "[vout]"
    else:
        map_video = "[v]"

    return [
        "ffmpeg", "-y", "-i", str(input_path),
        "-filter_complex", filters,
        "-map", map_video, "-map", "0:a?",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]


LAYOUT_MAP = {
    "blur": _blur_bg_cmd,
    "center": _center_crop_cmd,
    "stacked": _stacked_cmd,
}


async def reframe(
    input_path: Path,
    output_path: Path,
    layout: str = "blur",
    subtitle_path: Path | None = None,
) -> bool:
    """Run FFmpeg reframe asynchronously. Returns True on success."""
    cmd_fn = LAYOUT_MAP.get(layout, _blur_bg_cmd)
    cmd = cmd_fn(input_path, output_path, subtitle_path)

    logger.info("FFmpeg reframe [%s]: %s -> %s", layout, input_path.name, output_path.name)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error("FFmpeg failed (rc=%d): %s", proc.returncode, stderr.decode()[-500:])
            return False

        logger.info("FFmpeg done: %s (%.1f MB)", output_path.name, output_path.stat().st_size / 1e6)
        return True

    except Exception as e:
        logger.error("FFmpeg error: %s", e)
        return False


async def loudnorm(input_path: Path, output_path: Path) -> bool:
    """Normalize audio to -14 LUFS (platform standard)."""
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", "loudnorm=I=-14:TP=-1:LRA=11",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        str(output_path),
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error("loudnorm failed: %s", stderr.decode()[-300:])
            return False
        return True
    except Exception as e:
        logger.error("loudnorm error: %s", e)
        return False

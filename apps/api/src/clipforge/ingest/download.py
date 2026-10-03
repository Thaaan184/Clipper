"""Download low-bitrate audio and live chat replay."""

import asyncio
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import structlog
import yt_dlp

from clipforge.core.errors import DiskSpaceError, StageExecutionError
from clipforge.ingest.models import IngestResult, VideoMetadata

logger = structlog.get_logger(__name__)


def check_disk_preflight(
    dest_dir: Path,
    duration_s: float,
    bitrate_kbps: int = 96,
    safety_margin_gb: float = 2.0,
) -> int:
    """
    Ensure disk has enough space: >= 2 * estimated_audio_size + safety_margin_gb.

    Returns:
        Estimated audio size in bytes.
    """
    estimated_bytes = int(duration_s * (bitrate_kbps * 1000 / 8))
    required_bytes = int(2 * estimated_bytes + (safety_margin_gb * 1024 * 1024 * 1024))

    dest_dir.mkdir(parents=True, exist_ok=True)
    total, used, free = shutil.disk_usage(dest_dir)

    if free < required_bytes:
        raise DiskSpaceError(
            f"Insufficient disk space in {dest_dir}. Required {required_bytes / (1024**3):.2f} GB "
            f"(2x est {estimated_bytes / (1024**2):.1f}MB + {safety_margin_gb}GB reserve), "
            f"but only {free / (1024**3):.2f} GB free."
        )

    return estimated_bytes


def _verify_audio_stream(audio_file: Path) -> bool:
    """Verify downloaded audio file has a valid audio stream using ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=codec_name,duration,channels,sample_rate",
        "-of",
        "json",
        str(audio_file),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(proc.stdout)
        streams = data.get("streams", [])
        return len(streams) > 0
    except Exception as exc:
        logger.warning("ffprobe_audio_validation_failed", path=str(audio_file), error=str(exc))
        return False


def _download_sync(
    metadata: VideoMetadata,
    output_dir: Path,
    cookies_path: Path | None = None,
) -> IngestResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_out_tmpl = str(output_dir / "audio_raw.%(ext)s")

    ydl_opts: dict[str, Any] = {
        "format": "bestaudio[abr<=96]/bestaudio/worstaudio",
        "outtmpl": audio_out_tmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 5,
    }
    if cookies_path and cookies_path.exists():
        ydl_opts["cookiefile"] = str(cookies_path)

    # 1. Download audio stream
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([metadata.canonical_url])
    except Exception as exc:
        raise StageExecutionError(f"Failed to download audio stream: {exc}") from exc

    # Find the downloaded audio file (can be .m4a, .webm, .opus, .mp3, etc.)
    audio_candidates = list(output_dir.glob("audio_raw.*"))
    if not audio_candidates:
        raise StageExecutionError(f"Audio file was not created in {output_dir}")

    audio_file = audio_candidates[0]
    if not _verify_audio_stream(audio_file):
        raise StageExecutionError(
            f"Downloaded audio {audio_file.name} contains no valid audio stream"
        )

    # 2. Download live chat replay if available
    chat_path: str | None = None
    if metadata.has_chat:
        chat_opts: dict[str, Any] = {
            "skip_download": True,
            "writesubtitles": True,
            "subtitleslangs": ["live_chat"],
            "outtmpl": str(output_dir / "chat.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
        }
        if cookies_path and cookies_path.exists():
            chat_opts["cookiefile"] = str(cookies_path)
        try:
            with yt_dlp.YoutubeDL(chat_opts) as ydl:
                ydl.download([metadata.canonical_url])

            chat_candidates = list(output_dir.glob("chat.*.json*")) + list(
                output_dir.glob("chat.*")
            )
            for c in chat_candidates:
                if c.is_file() and c.stat().st_size > 0:
                    chat_path = str(c)
                    break
        except Exception as exc:
            logger.warning("live_chat_download_warning", error=str(exc))
            chat_path = None

    # 3. Save heatmap if available
    heatmap_path: str | None = None
    if metadata.heatmap_raw:
        hm_file = output_dir / "heatmap.json"
        hm_file.write_text(json.dumps(metadata.heatmap_raw, indent=2))
        heatmap_path = str(hm_file)

    disk_used = sum(f.stat().st_size for f in output_dir.glob("*") if f.is_file())

    return IngestResult(
        metadata=metadata,
        audio_path=str(audio_file),
        chat_path=chat_path,
        heatmap_path=heatmap_path,
        disk_used_bytes=disk_used,
    )


async def download_ingest_assets(
    metadata: VideoMetadata,
    output_dir: Path,
    cookies_path: Path | None = None,
) -> IngestResult:
    check_disk_preflight(output_dir, metadata.duration_s)
    return await asyncio.to_thread(
        _download_sync,
        metadata,
        output_dir,
        cookies_path,
    )

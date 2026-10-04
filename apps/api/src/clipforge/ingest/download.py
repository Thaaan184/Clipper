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


async def download_video_range(
    source_url: str,
    start_s: float,
    end_s: float,
    out_path: Path,
    pad_s: float = 3.0,
    cookies_path: Path | None = None,
) -> Path:
    """
    Download or extract a precise video segment for a candidate window with padding,
    then perform exact FFmpeg re-encode trimming to ensure accurate start and keyframes.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    duration = max(1.0, end_s - start_s)

    # Local file or test source
    if not source_url.startswith("http"):
        local_src = Path(source_url)
        if not local_src.exists():
            raise FileNotFoundError(f"Local video source not found: {source_url}")

        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{max(0.0, start_s):.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(local_src),
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-pix_fmt",
            "yuv420p",
            "-loglevel",
            "error",
            str(out_path),
        ]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError(
                f"FFmpeg trim failed: {proc.stderr.decode('utf-8', errors='replace')}"
            )
        return out_path

    temp_pad = out_path.parent / f"pad_{out_path.name}"
    ydl_opts: dict[str, Any] = {
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "outtmpl": str(temp_pad),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    if cookies_path and cookies_path.exists():
        ydl_opts["cookiefile"] = str(cookies_path)

    def _sync_download() -> float:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(source_url, download=False)
            has_fragments = False
            requested = info.get("requested_formats") or [info]
            for f in requested:
                frags = f.get("fragments")
                if frags and len(frags) > 1:
                    has_fragments = True
                    break

            if has_fragments:
                min_s_idx = None
                frag_dur = 5.0
                for f in requested:
                    frags = f.get("fragments", [])
                    if frags:
                        frag_dur = float(f.get("target_duration") or 5.0)
                        s_idx = max(0, int((start_s - pad_s) / frag_dur) - 1)
                        e_idx = min(len(frags), int((end_s + pad_s) / frag_dur) + 2)
                        f["fragments"] = frags[s_idx:e_idx]
                        if min_s_idx is None or s_idx < min_s_idx:
                            min_s_idx = s_idx
                ydl.process_ie_result(info, download=True)
                calc_offset = max(0.0, start_s - ((min_s_idx or 0) * frag_dur))
                return calc_offset
            else:
                def range_callback(info_dict: dict[str, Any], ydl_inst: Any) -> list[dict[str, Any]]:
                    return [
                        {
                            "start_time": max(0.0, start_s - pad_s),
                            "end_time": end_s + pad_s,
                        }
                    ]

                ydl.params["download_ranges"] = range_callback
                ydl.params["force_keyframes_at_cuts"] = True
                ydl.process_ie_result(info, download=True)
                return max(0.0, min(pad_s, start_s))

    loop = asyncio.get_running_loop()
    actual_offset = await loop.run_in_executor(None, _sync_download)

    # Now trim the exact segment from padded video
    padded_candidates = list(out_path.parent.glob(f"pad_{out_path.stem}*"))
    if not padded_candidates:
        raise FileNotFoundError("Padded download file not found")

    padded_file = padded_candidates[0]

    trim_cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{actual_offset:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(padded_file),
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-pix_fmt",
        "yuv420p",
        "-loglevel",
        "error",
        str(out_path),
    ]
    proc = subprocess.run(trim_cmd, capture_output=True)
    padded_file.unlink(missing_ok=True)

    if proc.returncode != 0:
        raise RuntimeError(
            f"Exact range trim failed: {proc.stderr.decode('utf-8', errors='replace')}"
        )

    return out_path


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

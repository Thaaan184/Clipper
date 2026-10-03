"""Probe video metadata using yt-dlp Python API."""

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import structlog
import yt_dlp

from clipforge.core.errors import (
    LiveInProgressError,
    RateLimitedError,
    VideoUnavailableError,
    VodTooLongError,
)
from clipforge.ingest.models import VideoMetadata
from clipforge.ingest.url import validate_and_canonicalize_url

logger = structlog.get_logger(__name__)


def _extract_heatmap(info: Mapping[str, Any] | Any) -> list[dict[str, Any]]:
    """Extract heatmap markers from yt-dlp info dict if present."""
    heatmap = info.get("heatmap")
    if heatmap and isinstance(heatmap, list):
        return heatmap

    # Some yt-dlp versions store in markers -> heatmap
    markers = info.get("markers")
    if markers and isinstance(markers, dict):
        hm = markers.get("heatmap")
        if hm and isinstance(hm, list):
            return hm

    return []


def _extract_formats_summary(formats: list[Any]) -> list[dict[str, Any]]:
    summary = []
    for f in formats:
        summary.append(
            {
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "vcodec": f.get("vcodec"),
                "acodec": f.get("acodec"),
                "abr": f.get("abr"),
                "vbr": f.get("vbr"),
                "filesize": f.get("filesize") or f.get("filesize_approx"),
            }
        )
    return summary


def _probe_sync(
    canonical_url: str,
    video_id: str,
    cookies_path: Path | None = None,
    max_duration_s: float = 36000.0,
) -> VideoMetadata:
    ydl_opts: dict[str, Any] = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "socket_timeout": 30,
        "retries": 3,
        "extract_flat": False,
    }
    if cookies_path and cookies_path.exists():
        ydl_opts["cookiefile"] = str(cookies_path)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(canonical_url, download=False)
    except Exception as exc:
        err_msg = str(exc)
        logger.error("yt_dlp_probe_failed", url=canonical_url, error=err_msg)
        if "429" in err_msg or "Too Many Requests" in err_msg:
            raise RateLimitedError(f"Rate limited by YouTube: {err_msg}") from exc
        if "Video unavailable" in err_msg or "Private video" in err_msg or "Sign in" in err_msg:
            raise VideoUnavailableError(f"Video unavailable or private: {err_msg}") from exc
        raise

    if not info:
        raise VideoUnavailableError(f"No metadata returned for video {video_id}")

    is_live = bool(info.get("is_live", False))
    live_status = str(info.get("live_status", ""))

    if is_live or live_status == "is_live":
        raise LiveInProgressError(
            f"Video {video_id} is currently broadcasting live. Please wait until the stream concludes."
        )

    duration = float(info.get("duration") or 0.0)
    if duration > max_duration_s:
        raise VodTooLongError(
            f"VOD duration ({duration:.1f}s) exceeds maximum configured limit ({max_duration_s:.1f}s)"
        )

    # Subtitles check
    subtitles = info.get("subtitles") or {}
    auto_captions = info.get("automatic_captions") or {}
    has_subtitles = bool(subtitles or auto_captions)

    # Chat replay check
    has_chat = "live_chat" in subtitles

    # Heatmap
    heatmap_raw = _extract_heatmap(info)
    has_heatmap = len(heatmap_raw) > 0

    formats = info.get("formats") or []
    formats_summary = _extract_formats_summary(formats)

    return VideoMetadata(
        video_id=video_id,
        canonical_url=canonical_url,
        title=info.get("title") or f"YouTube Video {video_id}",
        duration_s=duration,
        is_live=is_live,
        live_status=live_status,
        channel=info.get("channel") or info.get("uploader"),
        channel_id=info.get("channel_id") or info.get("uploader_id"),
        upload_date=info.get("upload_date"),
        has_chat=has_chat,
        has_subtitles=has_subtitles,
        has_heatmap=has_heatmap,
        formats_summary=formats_summary,
        heatmap_raw=heatmap_raw,
    )


async def probe_video(
    url: str,
    cookies_path: Path | None = None,
    max_duration_s: float = 36000.0,
) -> VideoMetadata:
    canonical_url, video_id = validate_and_canonicalize_url(url)
    return await asyncio.to_thread(
        _probe_sync,
        canonical_url,
        video_id,
        cookies_path,
        max_duration_s,
    )

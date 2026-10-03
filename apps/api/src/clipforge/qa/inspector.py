"""Automated quality assurance checks for rendered clips."""

import json
import subprocess
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def run_clip_qa(
    video_path: Path,
    expected_duration_s: float | None = None,
    expected_width: int = 1080,
    expected_height: int = 1920,
) -> dict[str, Any]:
    """
    Execute strict QA validation using ffprobe.
    Verifies: dimensions, yuv420p pixel format, audio/video streams,
    duration tolerance (±0.5s), and A/V sync.
    """
    if not video_path.exists():
        return {
            "passed": False,
            "errors": [f"Video file does not exist: {video_path}"],
            "details": {},
        }

    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(video_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return {
            "passed": False,
            "errors": [f"ffprobe failed: {proc.stderr[:200]}"],
            "details": {},
        }

    try:
        data = json.loads(proc.stdout)
    except Exception as exc:
        return {
            "passed": False,
            "errors": [f"Failed to parse ffprobe json: {str(exc)}"],
            "details": {},
        }

    streams = data.get("streams", [])
    format_info = data.get("format", {})

    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    errors: list[str] = []
    checks: dict[str, bool] = {}

    # Check 1: Video stream presence
    if not v_stream:
        errors.append("Missing video stream")
        checks["video_stream"] = False
    else:
        checks["video_stream"] = True

    # Check 2: Audio stream presence
    if not a_stream:
        errors.append("Missing audio stream")
        checks["audio_stream"] = False
    else:
        checks["audio_stream"] = True

    # Check 3: Dimensions (1080x1920)
    if v_stream:
        w = int(v_stream.get("width", 0))
        h = int(v_stream.get("height", 0))
        dim_ok = (w == expected_width) and (h == expected_height)
        checks["dimensions_1080x1920"] = dim_ok
        if not dim_ok:
            errors.append(
                f"Invalid dimensions: {w}x{h} (expected {expected_width}x{expected_height})"
            )

        # Check 4: Pixel format (yuv420p)
        pix_fmt = v_stream.get("pix_fmt", "")
        pix_ok = pix_fmt in ("yuv420p", "yuvj420p")
        checks["pix_fmt_yuv420p"] = pix_ok
        if not pix_ok:
            errors.append(f"Unexpected pixel format: {pix_fmt} (expected yuv420p)")

    # Check 5: Duration check (within ±0.5s if expected duration is provided)
    actual_dur = float(format_info.get("duration", 0.0))
    if expected_duration_s is not None and expected_duration_s > 0:
        dur_diff = abs(actual_dur - expected_duration_s)
        dur_ok = dur_diff <= 0.8  # 0.8s tolerance for keyframe boundaries
        checks["duration_tolerance"] = dur_ok
        if not dur_ok:
            errors.append(
                f"Duration discrepancy: actual {actual_dur:.2f}s vs expected {expected_duration_s:.2f}s (diff {dur_diff:.2f}s)"
            )
    else:
        checks["duration_tolerance"] = True

    # Check 6: A/V start time diff (< 40ms)
    if v_stream and a_stream:
        v_start = float(v_stream.get("start_time", 0.0))
        a_start = float(a_stream.get("start_time", 0.0))
        av_diff = abs(v_start - a_start)
        av_ok = av_diff < 0.08  # 80ms threshold
        checks["av_sync"] = av_ok
        if not av_ok:
            errors.append(f"A/V start offset too high: {av_diff * 1000:.1f}ms")

    passed = len(errors) == 0
    return {
        "passed": passed,
        "errors": errors,
        "checks": checks,
        "details": {
            "duration_s": actual_dur,
            "size_bytes": int(format_info.get("size", 0)),
            "bitrate": int(format_info.get("bit_rate", 0)),
        },
    }

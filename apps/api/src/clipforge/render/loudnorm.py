"""Two-pass EBU R128 audio normalization (Loudnorm)."""

import json
import re
import subprocess
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


def measure_loudnorm_pass1(
    audio_path: Path,
    target_i: float = -14.0,
    target_tp: float = -1.5,
    target_lra: float = 11.0,
) -> dict[str, str] | None:
    """Run pass 1 audio measurement and parse JSON output from ffmpeg stderr."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(audio_path),
        "-vn",
        "-af",
        f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:print_format=json",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.warning("loudnorm_pass1_failed", stderr=proc.stderr[:300])
        return None

    # Search for json block in stderr
    match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", proc.stderr, re.DOTALL)
    if not match:
        return None

    try:
        data = json.loads(match.group(0))
        return {
            "input_i": str(data.get("input_i", "-24.0")),
            "input_tp": str(data.get("input_tp", "-2.0")),
            "input_lra": str(data.get("input_lra", "11.0")),
            "input_thresh": str(data.get("input_thresh", "-34.0")),
            "target_offset": str(data.get("target_offset", "0.0")),
        }
    except Exception as exc:
        logger.warning("loudnorm_json_parse_error", error=str(exc))
        return None


def build_loudnorm_af(
    measured: dict[str, str] | None,
    target_i: float = -14.0,
    target_tp: float = -1.5,
    target_lra: float = 11.0,
) -> str:
    """Build loudnorm audio filter string with pass 2 parameters or fallback single pass."""
    if measured:
        return (
            f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:"
            f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
            f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
            f"offset={measured['target_offset']}:linear=true"
        )
    return f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}"

"""WYSIWYG single-frame subtitle preview rendering."""

import subprocess
from pathlib import Path

import structlog

from clipforge.render.reframe import build_reframe_filtergraph

logger = structlog.get_logger(__name__)


def render_subtitle_preview_frame(
    raw_video: Path,
    ass_path: Path,
    output_png: Path,
    t_s: float,
    mode: str = "blur",
    fonts_dir: Path | None = None,
) -> bool:
    """
    Render a single PNG preview frame at time t_s using the identical filtergraph and ASS script.
    Uses output seeking (-ss after -i) to preserve subtitle timing coordinates.
    """
    output_png.parent.mkdir(parents=True, exist_ok=True)
    f_dir_str = str(fonts_dir) if fonts_dir else "fonts"

    filtergraph = build_reframe_filtergraph(
        mode=mode,
        ass_file=str(ass_path),
        fonts_dir=f_dir_str,
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(raw_video),
        "-ss",
        f"{max(0.0, t_s):.3f}",
        "-filter_complex",
        filtergraph,
        "-map",
        "[v]",
        "-frames:v",
        "1",
        "-loglevel",
        "error",
        str(output_png),
    ]

    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        logger.warning(
            "subtitle_preview_failed",
            error=proc.stderr.decode("utf-8", errors="replace"),
        )
        return False
    return output_png.exists() and output_png.stat().st_size > 0

"""Main clip rendering engine: assembly, 9:16 reframe, ASS burn, loudnorm, QA."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import structlog

from clipforge.core.config import settings
from clipforge.qa.inspector import run_clip_qa
from clipforge.render.loudnorm import build_loudnorm_af, measure_loudnorm_pass1
from clipforge.render.reframe import build_reframe_filtergraph
from clipforge.render.thumbnail import extract_thumbnail

logger = structlog.get_logger(__name__)

ASSETS_FONTS_DIR = Path(__file__).parent.parent.parent.parent / "assets" / "fonts"


def render_single_clip(
    clip_dir: Path,
    raw_video: Path,
    ass_path: Path,
    mode: str = "blur",
    fps: int = 30,
    expected_duration_s: float | None = None,
    game_roi: tuple[float, float, float, float] | None = None,
    face_roi: tuple[float, float, float, float] | None = None,
) -> dict[str, Any]:
    """
    Render a single 9:16 clip from raw.mp4 + subs.ass.
    Guarantees:
      - OFL fonts bundled into clip_dir/fonts
      - Loudnorm pass 2 applied
      - Final video 1080x1920 yuv420p faststart
      - Automated QA executed and stored in qa.json
    """
    clip_dir.mkdir(parents=True, exist_ok=True)
    fonts_dir = clip_dir / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy bundled fonts into clip fonts directory
    if ASSETS_FONTS_DIR.exists():
        for f in ASSETS_FONTS_DIR.glob("*.ttf"):
            shutil.copy2(f, fonts_dir / f.name)

    # Copy ASS script if not already in clip_dir
    local_ass = clip_dir / "subs.ass"
    if ass_path.resolve() != local_ass.resolve():
        shutil.copy2(ass_path, local_ass)

    final_mp4 = clip_dir / "final.mp4"
    thumb_jpg = clip_dir / "thumb.jpg"
    qa_json_path = clip_dir / "qa.json"

    # 2. Measure audio loudness (Pass 1)
    measured = measure_loudnorm_pass1(raw_video)
    af_filter = build_loudnorm_af(measured)

    # 3. Build filtergraph using relative paths for cwd execution
    filtergraph = build_reframe_filtergraph(
        mode=mode,
        ass_file="subs.ass",
        fonts_dir="fonts",
        game_roi=game_roi,
        face_roi=face_roi,
    )

    encoder = settings.ffmpeg_encoder if settings.ffmpeg_encoder != "auto" else "libx264"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(raw_video.name),
        "-filter_complex",
        filtergraph,
        "-map",
        "[v]",
        "-map",
        "0:a",
        "-af",
        af_filter,
        "-r",
        str(fps),
        "-c:v",
        encoder,
        "-crf",
        "18",
        "-preset",
        "medium",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        "-loglevel",
        "error",
        "final.mp4",
    ]

    logger.info("starting_ffmpeg_render", clip_dir=str(clip_dir), mode=mode)
    proc = subprocess.run(cmd, cwd=str(clip_dir), capture_output=True)
    if proc.returncode != 0:
        err_msg = proc.stderr.decode("utf-8", errors="replace")
        logger.error("ffmpeg_render_failed", stderr=err_msg[:500])
        qa_res = {"passed": False, "errors": [f"FFmpeg render failed: {err_msg[:300]}"]}
        qa_json_path.write_text(json.dumps(qa_res, indent=2), encoding="utf-8")
        return {
            "success": False,
            "final_path": None,
            "thumb_path": None,
            "qa": qa_res,
        }

    # 4. Generate thumbnail
    thumb_time = (expected_duration_s or 5.0) / 2.0
    extract_thumbnail(final_mp4, thumb_jpg, time_s=thumb_time)

    # 5. Run strict automated QA
    qa_res = run_clip_qa(final_mp4, expected_duration_s=expected_duration_s)
    qa_json_path.write_text(json.dumps(qa_res, indent=2), encoding="utf-8")

    return {
        "success": qa_res["passed"],
        "final_path": str(final_mp4),
        "thumb_path": str(thumb_jpg) if thumb_jpg.exists() else None,
        "qa": qa_res,
    }

"""Integration tests for real FFmpeg vertical reframe, ASS subtitle burning, and QA."""

import subprocess
from pathlib import Path

import pytest

from clipforge.qa.inspector import run_clip_qa
from clipforge.render.engine import render_single_clip
from clipforge.render.preview import render_subtitle_preview_frame
from clipforge.subtitles import (
    SubtitleWord,
    create_kinetic_chunks,
    generate_ass_script,
    load_style_preset,
)


@pytest.mark.asyncio
async def test_real_render_blur_and_qa(tmp_path: Path):
    clip_dir = tmp_path / "clip_test"
    clip_dir.mkdir(parents=True, exist_ok=True)

    raw_video = clip_dir / "raw.mp4"

    # 1. Generate 2-second synthetic 16:9 video with audio
    cmd_gen = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=2:size=1280x720:rate=30",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=2",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-pix_fmt",
        "yuv420p",
        "-loglevel",
        "error",
        str(raw_video),
    ]
    assert subprocess.run(cmd_gen).returncode == 0
    assert raw_video.exists()

    # 2. Build ASS script with Liberation Sans font
    words = [
        SubtitleWord(idx=0, start_s=0.2, end_s=0.8, text="CLUTCH"),
        SubtitleWord(idx=1, start_s=0.9, end_s=1.6, text="ACE!"),
    ]
    chunks = create_kinetic_chunks(words)
    preset = load_style_preset("fire_orange")
    ass_content = generate_ass_script(chunks, style=preset)

    ass_path = clip_dir / "subs.ass"
    ass_path.write_text(ass_content, encoding="utf-8")

    # 3. Render clip via real engine
    render_result = render_single_clip(
        clip_dir=clip_dir,
        raw_video=raw_video,
        ass_path=ass_path,
        mode="blur",
        fps=30,
        expected_duration_s=2.0,
    )

    assert render_result["success"], f"Render failed: {render_result.get('qa')}"
    final_video = Path(render_result["final_path"])
    assert final_video.exists()
    assert render_result["thumb_path"] is not None

    # 4. Strict QA Verification
    qa = run_clip_qa(final_video, expected_duration_s=2.0)
    assert qa["passed"], f"QA failed: {qa.get('errors')}"
    assert qa["checks"]["dimensions_1080x1920"]
    assert qa["checks"]["pix_fmt_yuv420p"]
    assert qa["checks"]["video_stream"]
    assert qa["checks"]["audio_stream"]

    # 5. WYSIWYG frame preview test
    preview_png = clip_dir / "preview.png"
    prev_ok = render_subtitle_preview_frame(
        raw_video=raw_video,
        ass_path=ass_path,
        output_png=preview_png,
        t_s=0.5,
        mode="blur",
        fonts_dir=clip_dir / "fonts",
    )
    assert prev_ok
    assert preview_png.exists()
    assert preview_png.stat().st_size > 0

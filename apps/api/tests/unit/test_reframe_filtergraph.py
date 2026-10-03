"""Unit tests for FFmpeg reframe filtergraph construction."""

from clipforge.render.reframe import build_reframe_filtergraph


def test_reframe_blur_filtergraph():
    fg = build_reframe_filtergraph(mode="blur", ass_file="subs.ass", fonts_dir="fonts")
    assert "gblur=sigma=30" in fg
    assert "overlay=(W-w)/2:(H-h)/2" in fg
    assert "ass=subs.ass:fontsdir=fonts" in fg
    assert "format=yuv420p" in fg


def test_reframe_center_crop_filtergraph():
    fg = build_reframe_filtergraph(mode="center", ass_file="subs.ass", fonts_dir="fonts")
    assert "crop=1080:1920" in fg
    assert "ass=subs.ass:fontsdir=fonts" in fg


def test_reframe_stacked_filtergraph():
    fg = build_reframe_filtergraph(
        mode="stacked",
        ass_file="subs.ass",
        fonts_dir="fonts",
        game_roi=(0.0, 0.0, 1.0, 0.7),
        face_roi=(0.7, 0.7, 0.3, 0.3),
    )
    assert "vstack=inputs=2" in fg
    assert "scale=1080:1200" in fg
    assert "scale=1080:720" in fg

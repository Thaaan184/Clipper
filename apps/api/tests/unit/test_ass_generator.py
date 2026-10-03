"""Unit tests for deterministic ASS script generation."""

from clipforge.subtitles.ass_builder import (
    format_ass_centisecond,
    generate_ass_script,
    load_style_preset,
)
from clipforge.subtitles.models import SubtitleChunk, SubtitleWord


def test_format_ass_centisecond():
    assert format_ass_centisecond(0.0) == "0:00:00.00"
    assert format_ass_centisecond(1.234) == "0:00:01.23"
    assert format_ass_centisecond(65.5) == "0:01:05.50"
    assert format_ass_centisecond(3661.05) == "1:01:01.05"


def test_load_all_presets():
    for name in [
        "classic_white",
        "hormozi_bold",
        "mrbeast_box",
        "neon_glow",
        "minimal_clean",
        "fire_orange",
    ]:
        preset = load_style_preset(name)
        assert preset.name == name
        assert preset.font_size > 0
        assert "&H" in preset.primary_color


def test_generate_ass_script_active_word_highlighting():
    words = [
        SubtitleWord(idx=0, start_s=1.0, end_s=1.5, text="squad"),
        SubtitleWord(idx=1, start_s=1.5, end_s=2.0, text="wipe"),
    ]
    chunk = SubtitleChunk(words=words, start_s=1.0, end_s=2.0)
    preset = load_style_preset("classic_white")

    ass_text = generate_ass_script([chunk], style=preset)
    assert "PlayResX: 1080" in ass_text
    assert "PlayResY: 1920" in ass_text
    assert "Style: Default" in ass_text

    # Should have two Dialogue lines for 2 words
    dialogue_lines = [ln for ln in ass_text.splitlines() if ln.startswith("Dialogue:")]
    assert len(dialogue_lines) == 2

    # First event highlights squad
    assert "{\\c&H00008CFF&}squad{\\r} wipe" in dialogue_lines[0]
    # Second event highlights wipe
    assert "squad {\\c&H00008CFF&}wipe{\\r}" in dialogue_lines[1]

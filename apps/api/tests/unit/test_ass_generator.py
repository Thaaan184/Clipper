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
        "none",
    ]:
        preset = load_style_preset(name)
        assert preset.name == name
        assert preset.font_size > 0
        assert "&H" in preset.primary_color


def test_generate_ass_script_none_preset():
    words = [
        SubtitleWord(idx=0, start_s=1.0, end_s=1.5, text="squad"),
    ]
    chunk = SubtitleChunk(words=words, start_s=1.0, end_s=1.5)
    preset = load_style_preset("none")

    ass_text = generate_ass_script([chunk], style=preset)
    assert "PlayResX: 1080" in ass_text
    dialogue_lines = [ln for ln in ass_text.splitlines() if ln.startswith("Dialogue:")]
    assert len(dialogue_lines) == 0


def test_generate_ass_script_active_word_highlighting():
    words = [
        SubtitleWord(idx=0, start_s=1.0, end_s=1.5, text="squad"),
        SubtitleWord(idx=1, start_s=1.5, end_s=2.0, text="wipe"),
    ]
    chunk = SubtitleChunk(words=words, start_s=1.0, end_s=2.0)

    # 1. Fire Orange style highlights with &H00008CFF&
    orange_preset = load_style_preset("fire_orange")
    orange_ass = generate_ass_script([chunk], style=orange_preset)
    orange_lines = [ln for ln in orange_ass.splitlines() if ln.startswith("Dialogue:")]
    assert len(orange_lines) == 2
    assert "{\\c&H00008CFF&}squad{\\r} wipe" in orange_lines[0]
    assert "squad {\\c&H00008CFF&}wipe{\\r}" in orange_lines[1]

    # 2. Classic White stays clean white without orange tags
    white_preset = load_style_preset("classic_white")
    white_ass = generate_ass_script([chunk], style=white_preset)
    white_lines = [ln for ln in white_ass.splitlines() if ln.startswith("Dialogue:")]
    assert len(white_lines) == 2
    assert "&H00008CFF&" not in white_ass
    assert "squad wipe" in white_lines[0]

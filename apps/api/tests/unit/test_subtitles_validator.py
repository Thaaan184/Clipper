"""Unit tests for subtitle word validation, normalization, and escaping."""

from clipforge.subtitles.models import SubtitleWord
from clipforge.subtitles.validator import normalize_subtitle_text, validate_and_normalize_words


def test_normalize_subtitle_text():
    # Strips brackets, slashes, control chars, and emojis
    raw = "Halo {bro}! \\n Ini \u200bkeren 🔥👍"
    cleaned = normalize_subtitle_text(raw)
    assert "{" not in cleaned
    assert "}" not in cleaned
    assert "\\" not in cleaned
    assert "🔥" not in cleaned
    assert "👍" not in cleaned
    assert cleaned == "Halo bro! n Ini keren"


def test_validate_and_normalize_words_invariants():
    words = [
        SubtitleWord(idx=0, start_s=2.0, end_s=3.0, text="pertama"),
        SubtitleWord(idx=1, start_s=2.5, end_s=4.0, text="kedua"),  # overlaps with first
        SubtitleWord(idx=2, start_s=1.0, end_s=1.2, text="sebelumnya"),  # out of order
        SubtitleWord(idx=3, start_s=10.0, end_s=10.01, text="singkat"),  # too short (<40ms)
        SubtitleWord(idx=4, start_s=50.0, end_s=65.0, text="lewat"),  # exceeds 60s
    ]

    val = validate_and_normalize_words(words, clip_duration_s=60.0)
    # Check monotonicity
    for i in range(1, len(val)):
        assert val[i].start_s >= val[i - 1].start_s

    # Check clamped within clip duration
    for w in val:
        assert 0.0 <= w.start_s <= 60.0
        assert 0.0 <= w.end_s <= 60.0
        assert w.end_s >= w.start_s + 0.04

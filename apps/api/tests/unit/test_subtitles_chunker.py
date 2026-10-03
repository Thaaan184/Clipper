"""Unit tests for kinetic subtitle chunking."""

from clipforge.subtitles.chunker import create_kinetic_chunks
from clipforge.subtitles.models import SubtitleWord


def test_chunker_breaks_on_max_words():
    # 6 words in a row without pause
    words = [
        SubtitleWord(idx=i, start_s=float(i), end_s=float(i) + 0.8, text=f"kata{i}")
        for i in range(6)
    ]
    chunks = create_kinetic_chunks(words, max_words_per_chunk=4)
    assert len(chunks) == 2
    assert len(chunks[0].words) == 4
    assert len(chunks[1].words) == 2


def test_chunker_breaks_on_pause():
    words = [
        SubtitleWord(idx=0, start_s=1.0, end_s=1.5, text="halo"),
        SubtitleWord(idx=1, start_s=2.2, end_s=2.7, text="semua"),  # pause 0.7s >= 0.35s
    ]
    chunks = create_kinetic_chunks(words, max_pause_s=0.35)
    assert len(chunks) == 2


def test_chunker_breaks_on_punctuation():
    words = [
        SubtitleWord(idx=0, start_s=1.0, end_s=1.5, text="mantap!"),
        SubtitleWord(idx=1, start_s=1.6, end_s=2.0, text="gaspoll"),
    ]
    chunks = create_kinetic_chunks(words)
    assert len(chunks) == 2
    assert chunks[0].words[0].text == "mantap!"

"""Unit tests for word and sentence boundary snapping."""

from clipforge.asr.models import WordTimestamp
from clipforge.boundaries.snap import snap_boundaries_to_words
from clipforge.fusion.models import CandidateWindow


def test_snap_to_word_start_and_punct_end():
    cand = CandidateWindow(
        id="c1",
        rank=1,
        start_s=10.2,
        end_s=30.4,
        peak_s=20.0,
        duration_s=20.2,
        signal_score=0.8,
        final_score=0.8,
    )

    words = [
        WordTimestamp(idx=0, start_s=9.8, end_s=10.5, text="musuh"),
        WordTimestamp(idx=1, start_s=10.6, end_s=11.2, text="datang"),
        WordTimestamp(idx=2, start_s=29.0, end_s=29.8, text="rata"),
        WordTimestamp(idx=3, start_s=30.0, end_s=30.8, text="semua!"),
        WordTimestamp(idx=4, start_s=32.0, end_s=33.0, text="aman"),
    ]

    res = snap_boundaries_to_words(cand, words)
    # Start should snap to word closest to 10.2 (start_s 9.8 is 0.4 away, 10.6 is 0.4 away -> 9.8)
    assert res.start_s in (9.8, 10.6)
    # End should snap to word with punctuation: "semua!" at end_s 30.8
    assert res.end_s == 30.8
    assert 15.0 <= res.duration_s <= 60.0


def test_snap_clamps_duration_invariants():
    cand = CandidateWindow(
        id="c2",
        rank=1,
        start_s=10.0,
        end_s=15.0,  # too short (5s)
        peak_s=12.0,
        duration_s=5.0,
        signal_score=0.8,
        final_score=0.8,
    )

    words = [
        WordTimestamp(idx=0, start_s=10.0, end_s=11.0, text="halo"),
        WordTimestamp(idx=1, start_s=14.0, end_s=15.0, text="halo"),
    ]

    res = snap_boundaries_to_words(cand, words, min_duration=15.0)
    assert res.duration_s >= 15.0

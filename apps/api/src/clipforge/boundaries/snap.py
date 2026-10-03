"""Boundary snapping using word-level timestamps and punctuation."""

from clipforge.asr.models import WordTimestamp
from clipforge.fusion.models import CandidateWindow


def snap_boundaries_to_words(
    cand: CandidateWindow,
    words: list[WordTimestamp],
    min_duration: float = 15.0,
    max_duration: float = 60.0,
    max_start_shift_left: float = 3.0,
    max_start_shift_right: float = 1.5,
    max_end_shift_left: float = 1.0,
    max_end_shift_right: float = 3.0,
) -> CandidateWindow:
    """
    Refine candidate start and end timestamps against word boundaries and sentence endings.
    """
    if not words:
        return cand

    orig_start = cand.start_s
    orig_end = cand.end_s

    # Find candidate start words in search window [orig_start - shift_left, orig_start + shift_right]
    start_candidates = [
        w
        for w in words
        if (orig_start - max_start_shift_left) <= w.start_s <= (orig_start + max_start_shift_right)
    ]

    best_start = orig_start
    if start_candidates:
        # Prefer word following punctuation or closest word start
        best_w = min(start_candidates, key=lambda w: abs(w.start_s - orig_start))
        best_start = round(best_w.start_s, 2)

    # Find candidate end words in search window [orig_end - shift_left, orig_end + shift_right]
    end_candidates = [
        w
        for w in words
        if (orig_end - max_end_shift_left) <= w.end_s <= (orig_end + max_end_shift_right)
    ]

    best_end = orig_end
    if end_candidates:
        # Prefer word with terminal punctuation (. ? !)
        punct_ends = [w for w in end_candidates if any(w.text.endswith(p) for p in [".", "!", "?"])]
        if punct_ends:
            best_w = min(punct_ends, key=lambda w: abs(w.end_s - orig_end))
        else:
            best_w = min(end_candidates, key=lambda w: abs(w.end_s - orig_end))
        best_end = round(best_w.end_s, 2)

    # Invariant: Duration constraints
    new_dur = best_end - best_start
    if new_dur < min_duration:
        # Extend end or revert
        best_end = best_start + min_duration
    elif new_dur > max_duration:
        # Clamp to max
        best_end = best_start + max_duration

    cand.start_s = best_start
    cand.end_s = round(best_end, 2)
    cand.duration_s = round(cand.end_s - cand.start_s, 2)
    return cand

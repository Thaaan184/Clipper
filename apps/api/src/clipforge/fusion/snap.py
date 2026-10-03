"""Speech boundary snapping and invariant enforcement."""

from clipforge.signals.models import SpeechSegment


def snap_to_silence(
    timestamp_s: float,
    speech_segments: list[SpeechSegment],
    radius_s: float = 1.5,
    prefer_after: bool = False,
) -> float | None:
    """
    Snap a timestamp to the nearest silence / speech boundary within radius_s.
    """
    if not speech_segments:
        return None

    best_candidate: float | None = None
    min_dist = float("inf")

    # Check boundaries of speech segments
    for seg in speech_segments:
        for boundary in (seg.start_s, seg.end_s):
            dist = abs(timestamp_s - boundary)
            if dist <= radius_s and dist < min_dist:
                min_dist = dist
                best_candidate = boundary

    return best_candidate


def refine_boundaries(
    start_s: float,
    end_s: float,
    speech_segments: list[SpeechSegment],
    total_duration_s: float,
    min_duration_s: float = 15.0,
    max_duration_s: float = 60.0,
    tail_s: float = 0.4,
) -> tuple[float, float]:
    """
    Refine start and end boundaries using speech segments / silence gaps.
    Every shift is bounded and preserves duration invariants.
    """
    new_start = start_s
    new_end = end_s

    # Snap start to silence
    snapped_start = snap_to_silence(start_s, speech_segments, radius_s=1.5)
    if snapped_start is not None:
        new_start = snapped_start

    # Snap end to silence and add tail_s
    snapped_end = snap_to_silence(end_s, speech_segments, radius_s=1.5)
    if snapped_end is not None:
        new_end = snapped_end + tail_s
    else:
        new_end = end_s + tail_s

    # Clamp boundaries to video length
    new_start = max(0.0, min(new_start, total_duration_s))
    new_end = max(new_start + 1.0, min(new_end, total_duration_s))

    # Clamp duration to [min_duration_s, max_duration_s]
    dur = new_end - new_start
    if dur < min_duration_s:
        diff = min_duration_s - dur
        # Expand backwards first
        pre_exp = min(new_start, diff * 0.7)
        post_exp = min(total_duration_s - new_end, diff - pre_exp)
        new_start -= pre_exp
        new_end += post_exp

    elif dur > max_duration_s:
        excess = dur - max_duration_s
        # Trim from ends proportionally
        new_start += excess * 0.5
        new_end -= excess * 0.5

    # Final sanity bounds
    new_start = max(0.0, round(new_start, 2))
    new_end = min(total_duration_s, round(new_end, 2))

    if new_end <= new_start:
        new_end = min(total_duration_s, new_start + min_duration_s)

    return new_start, new_end

"""Unit tests for boundary snapping."""

from clipforge.fusion.snap import refine_boundaries, snap_to_silence
from clipforge.signals.models import SpeechSegment


def test_snap_to_silence():
    # Speech segment between 10.0s and 20.0s
    segments = [SpeechSegment(start_s=10.0, end_s=20.0, confidence=1.0)]

    # Boundary at 9.2s is within 1.5s of speech start (10.0s) -> should snap to 10.0s
    assert snap_to_silence(9.2, segments, radius_s=1.5) == 10.0
    # Boundary at 19.8s is within 1.5s of speech end (20.0s) -> should snap to 20.0s
    assert snap_to_silence(19.8, segments, radius_s=1.5) == 20.0
    # Boundary at 5.0s is far from speech -> None
    assert snap_to_silence(5.0, segments, radius_s=1.5) is None


def test_refine_boundaries_invariants():
    segments = [
        SpeechSegment(start_s=20.0, end_s=40.0, confidence=1.0),
    ]
    start, end = refine_boundaries(
        start_s=19.0,
        end_s=41.0,
        speech_segments=segments,
        total_duration_s=100.0,
        min_duration_s=15.0,
        max_duration_s=60.0,
        tail_s=0.4,
    )
    # Start snapped to 20.0, end snapped to 40.0 + 0.4 = 40.4
    assert start == 20.0
    assert end == 40.4
    assert 15.0 <= (end - start) <= 60.0

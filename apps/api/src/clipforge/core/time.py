"""Canonical timebase utilities for ClipForge v2.

Invariants:
- All domain timestamps are source_s (float seconds relative to source VOD start).
- Clip-local timestamps are clip_s (0.0 = first frame of the clip).
- Conversions are explicit and deterministic.
"""


def to_clip_time(source_s: float, clip_start_s: float) -> float:
    """Convert absolute source VOD seconds to clip-local seconds."""
    return round(max(0.0, source_s - clip_start_s), 3)


def to_source_time(clip_s: float, clip_start_s: float) -> float:
    """Convert clip-local seconds to absolute source VOD seconds."""
    return round(max(0.0, clip_s + clip_start_s), 3)


def format_ass_timestamp(seconds: float) -> str:
    """Format float seconds to ASS centisecond timestamp H:MM:SS.cc."""
    sec = max(0.0, seconds)
    total_cs = int(round(sec * 100))
    cs = total_cs % 100
    total_s = total_cs // 100
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def format_srt_timestamp(seconds: float) -> str:
    """Format float seconds to SRT millisecond timestamp HH:MM:SS,mmm."""
    sec = max(0.0, seconds)
    total_ms = int(round(sec * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

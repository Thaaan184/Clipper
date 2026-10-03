from clipforge.core.time import (
    format_ass_timestamp,
    format_srt_timestamp,
    to_clip_time,
    to_source_time,
)


def test_time_conversions():
    # 100s VOD, clip starts at 60s
    assert to_clip_time(60.0, 60.0) == 0.0
    assert to_clip_time(75.5, 60.0) == 15.5
    assert to_clip_time(50.0, 60.0) == 0.0  # clamp to 0.0

    assert to_source_time(0.0, 60.0) == 60.0
    assert to_source_time(15.5, 60.0) == 75.5


def test_format_ass_timestamp():
    assert format_ass_timestamp(0.0) == "0:00:00.00"
    assert format_ass_timestamp(65.43) == "0:01:05.43"
    assert format_ass_timestamp(3661.05) == "1:01:01.05"


def test_format_srt_timestamp():
    assert format_srt_timestamp(0.0) == "00:00:00,000"
    assert format_srt_timestamp(65.432) == "00:01:05,432"
    assert format_srt_timestamp(3661.005) == "01:01:01,005"

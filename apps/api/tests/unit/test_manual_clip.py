"""Comprehensive unit tests for:
1. Manual clipping timestamp parsing & validation
2. Subtitle preset colors (no unwanted orange fallback)
3. Subtitle timing editing (start/end timestamp changes flow into ASS & SRT)
"""

import pytest
from pydantic import ValidationError

from clipforge.api.routes.jobs import parse_timestamp_to_seconds
from clipforge.jobs.models import JobCreateRequest, ManualClipCreateRequest
from clipforge.subtitles import (
    SubtitleWord,
    create_kinetic_chunks,
    export_srt,
    generate_ass_script,
    load_style_preset,
    validate_and_normalize_words,
)


def test_parse_timestamp_to_seconds():
    # MM:SS format
    assert parse_timestamp_to_seconds("12:35") == 755.0
    assert parse_timestamp_to_seconds("14:20") == 860.0
    assert parse_timestamp_to_seconds("0:30") == 30.0
    assert parse_timestamp_to_seconds("00:00") == 0.0

    # HH:MM:SS format
    assert parse_timestamp_to_seconds("01:12:35") == 4355.0
    assert parse_timestamp_to_seconds("00:01:00") == 60.0
    assert parse_timestamp_to_seconds("02:00:00") == 7200.0

    # Float / seconds format
    assert parse_timestamp_to_seconds("45") == 45.0
    assert parse_timestamp_to_seconds("755.5") == 755.5
    assert parse_timestamp_to_seconds(120) == 120.0
    assert parse_timestamp_to_seconds(45.5) == 45.5

    # Invalid formats
    with pytest.raises(ValueError):
        parse_timestamp_to_seconds("")

    with pytest.raises(ValueError):
        parse_timestamp_to_seconds("invalid:time:format:extra")

    with pytest.raises(ValueError):
        parse_timestamp_to_seconds("abc")


def test_job_create_request_unpacks_nested_params():
    req = JobCreateRequest(
        source_url="https://www.youtube.com/watch?v=abcdef12345",
        params={
            "clip_count": 8,
            "reframe_mode": "center",
            "subtitle_style": "none",
        },
    )
    assert req.clip_count == 8
    assert req.reframe_mode == "center"
    assert req.subtitle_style == "none"


def test_manual_clip_create_request_validation():
    req = ManualClipCreateRequest(
        source_url="https://www.youtube.com/watch?v=abcdef12345",
        start_time="12:35",
        end_time="14:20",
        subtitle_style="none",
        reframe_mode="blur",
    )
    assert req.start_time == "12:35"
    assert req.end_time == "14:20"
    assert req.subtitle_style == "none"


def test_subtitle_presets_color_distinction():
    # Verify classic_white does NOT use orange highlight
    white_preset = load_style_preset("classic_white")
    assert white_preset.primary_color == "&H00FFFFFF&"
    assert white_preset.active_color == "&H00FFFFFF&"  # Stays pure white!

    # Verify fire_orange DOES use orange highlight
    orange_preset = load_style_preset("fire_orange")
    assert orange_preset.active_color == "&H00008CFF&"  # Orange in ASS format

    # Verify none preset
    none_preset = load_style_preset("none")
    assert none_preset.name.lower() == "none"
    chunks = create_kinetic_chunks(
        [SubtitleWord(idx=0, start_s=0.0, end_s=1.0, text="test")]
    )
    ass_none = generate_ass_script(chunks, style=none_preset)
    assert "Dialogue:" not in ass_none  # Zero subtitles burned!


def test_subtitle_editor_timestamp_changes_persist_to_ass_and_srt():
    # User edits timing from 12.5s -> 15.0s to 14.0s -> 17.5s
    edited_words = [
        SubtitleWord(
            idx=0,
            start_s=14.0,
            end_s=17.5,
            text="Ini adalah contoh subtitle yang sudah diedit.",
        )
    ]
    val_words = validate_and_normalize_words(edited_words, clip_duration_s=30.0)
    assert len(val_words) == 1
    assert val_words[0].start_s == 14.0
    assert val_words[0].end_s == 17.5
    assert val_words[0].text == "Ini adalah contoh subtitle yang sudah diedit."

    chunks = create_kinetic_chunks(val_words)
    srt_text = export_srt(chunks)
    assert "00:00:14,000 --> 00:00:17,500" in srt_text
    assert "Ini adalah contoh subtitle yang sudah diedit." in srt_text

    preset = load_style_preset("classic_white")
    ass_text = generate_ass_script(chunks, style=preset)
    assert "0:00:14.00,0:00:17.50" in ass_text
    assert "Ini adalah contoh subtitle yang sudah diedit." in ass_text


def test_subtitle_editor_multi_word_timing_edit():
    # User edits multiple words with custom timestamps
    words = [
        SubtitleWord(idx=0, start_s=2.0, end_s=3.5, text="Halo"),
        SubtitleWord(idx=1, start_s=4.0, end_s=6.2, text="Dunia"),
    ]
    val_words = validate_and_normalize_words(words, clip_duration_s=10.0)
    assert val_words[0].start_s == 2.0
    assert val_words[0].end_s == 3.5
    assert val_words[1].start_s == 4.0
    assert val_words[1].end_s == 6.2

    chunks = create_kinetic_chunks(val_words)
    srt_text = export_srt(chunks)
    assert "00:00:02,000 --> 00:00:03,500" in srt_text
    assert "00:00:04,000 --> 00:00:06,200" in srt_text

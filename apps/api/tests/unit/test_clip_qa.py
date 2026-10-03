"""Unit tests for automated clip QA inspector."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from clipforge.qa.inspector import run_clip_qa


def test_missing_video_fails_qa(tmp_path: Path):
    non_existent = tmp_path / "missing.mp4"
    res = run_clip_qa(non_existent)
    assert not res["passed"]
    assert "does not exist" in res["errors"][0]


def test_valid_ffprobe_output_passes_qa(tmp_path: Path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"dummy")

    mock_probe = {
        "streams": [
            {
                "codec_type": "video",
                "width": 1080,
                "height": 1920,
                "pix_fmt": "yuv420p",
                "start_time": "0.000",
            },
            {"codec_type": "audio", "start_time": "0.005"},
        ],
        "format": {"duration": "30.15", "size": "1048576", "bit_rate": "2500000"},
    }

    import json

    with patch("subprocess.run") as m_run:
        m_proc = MagicMock()
        m_proc.returncode = 0
        m_proc.stdout = json.dumps(mock_probe)
        m_run.return_value = m_proc

        res = run_clip_qa(video, expected_duration_s=30.0)
        assert res["passed"]
        assert len(res["errors"]) == 0
        assert res["checks"]["dimensions_1080x1920"]
        assert res["checks"]["pix_fmt_yuv420p"]

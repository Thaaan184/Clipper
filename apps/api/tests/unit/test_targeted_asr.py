"""Unit tests for targeted ASR candidate slicing and transcription."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from clipforge.asr.models import CandidateTranscript
from clipforge.asr.whisper import transcribe_candidate_slice
from clipforge.fusion.models import CandidateWindow


def test_missing_audio_returns_empty_transcript(tmp_path: Path):
    non_existent = tmp_path / "missing.opus"
    cand = CandidateWindow(
        id="c1",
        rank=1,
        start_s=10.0,
        end_s=30.0,
        peak_s=20.0,
        duration_s=20.0,
        signal_score=0.8,
        final_score=0.8,
    )
    res = transcribe_candidate_slice(non_existent, cand)
    assert isinstance(res, CandidateTranscript)
    assert res.candidate_id == "c1"
    assert len(res.words) == 0


def test_transcribe_candidate_slice_mocked(tmp_path: Path):
    dummy_audio = tmp_path / "audio_raw.opus"
    dummy_audio.write_bytes(b"dummy")

    cand = CandidateWindow(
        id="c2",
        rank=1,
        start_s=100.0,
        end_s=120.0,
        peak_s=110.0,
        duration_s=20.0,
        signal_score=0.9,
        final_score=0.9,
    )

    mock_word = MagicMock()
    mock_word.word = "squad"
    mock_word.start = 2.5
    mock_word.end = 3.0
    mock_word.probability = 0.95

    mock_seg = MagicMock()
    mock_seg.text = "squad wipe"
    mock_seg.words = [mock_word]

    mock_info = MagicMock()
    mock_info.language = "id"

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_seg], mock_info)

    with (
        patch("clipforge.asr.whisper.extract_audio_slice") as m_extract,
        patch("clipforge.asr.whisper.get_whisper_model", return_value=mock_model),
    ):
        # Return 16000 float values representing 1 second of audio
        import numpy as np

        m_extract.return_value = np.zeros(16000, dtype=np.float32)

        res = transcribe_candidate_slice(dummy_audio, cand, pad_s=1.0)
        assert res.candidate_id == "c2"
        assert res.language == "id"
        assert len(res.words) == 1
        # Check canonical timebase: slice_start = 100.0 - 1.0 = 99.0s. Word start = 99.0 + 2.5 = 101.5s
        assert res.words[0].text == "squad"
        assert res.words[0].start_s == 101.5
        assert res.words[0].end_s == 102.0

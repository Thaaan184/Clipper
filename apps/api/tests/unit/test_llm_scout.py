"""Unit tests for LLM Scout evaluation and fallback heuristics."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clipforge.asr.models import CandidateTranscript
from clipforge.fusion.models import CandidateWindow
from clipforge.ingest.models import VideoMetadata
from clipforge.llm.client import _build_heuristic_verdict, evaluate_candidate_scout
from clipforge.signals.models import AudioFeatures, ChatFeatures


def test_heuristic_verdict_talking_only_rejected():
    cand = CandidateWindow(
        id="c1",
        rank=1,
        start_s=0.0,
        end_s=30.0,
        peak_s=15.0,
        duration_s=30.0,
        signal_score=0.4,
        final_score=0.4,
        flags=["talking_only"],
    )
    tr = CandidateTranscript(candidate_id="c1", text="kita ngobrol santai aja")
    audio = AudioFeatures(
        duration_s=30.0,
        loud_db=[-30.0] * 30,
        loud_surge=[0.05] * 30,
        onset_density=[0.1] * 30,
        hf_ratio=[0.2] * 30,
        crest_db=[5.0] * 30,
        nonspeech_loud=[0.05] * 30,
        speech_prob=[0.95] * 30,
    )
    chat = ChatFeatures(available=False, duration_s=30.0)

    verdict = _build_heuristic_verdict(cand, tr, audio, chat)
    assert verdict.verdict == "REJECT"
    assert verdict.category == "talking_only"


def test_heuristic_verdict_combat_action_kept():
    cand = CandidateWindow(
        id="c2",
        rank=1,
        start_s=0.0,
        end_s=30.0,
        peak_s=15.0,
        duration_s=30.0,
        signal_score=0.9,
        final_score=0.9,
    )
    tr = CandidateTranscript(candidate_id="c2", text="squad rata semua nice")
    audio = AudioFeatures(
        duration_s=30.0,
        loud_db=[-10.0] * 30,
        loud_surge=[0.60] * 30,
        onset_density=[2.0] * 30,
        hf_ratio=[0.5] * 30,
        crest_db=[12.0] * 30,
        nonspeech_loud=[0.4] * 30,
        speech_prob=[0.5] * 30,
    )
    chat = ChatFeatures(available=False, duration_s=30.0)

    verdict = _build_heuristic_verdict(cand, tr, audio, chat)
    assert verdict.verdict == "KEEP"
    assert verdict.category == "gameplay_highlight"
    assert "combat_action" in verdict.flags


@pytest.mark.asyncio
async def test_evaluate_candidate_scout_mocked_llm():
    cand = CandidateWindow(
        id="c3",
        rank=1,
        start_s=10.0,
        end_s=40.0,
        peak_s=25.0,
        duration_s=30.0,
        signal_score=0.85,
        final_score=0.85,
    )
    tr = CandidateTranscript(candidate_id="c3", text="clutch 1 v 3 berhasil")
    meta = VideoMetadata(
        video_id="test_vid",
        canonical_url="https://youtube.com/watch?v=test_vid",
        title="Apex Stream Pro",
        duration_s=300.0,
    )
    audio = AudioFeatures(
        duration_s=50.0,
        loud_db=[-20.0] * 50,
        loud_surge=[0.4] * 50,
        onset_density=[1.5] * 50,
        hf_ratio=[0.3] * 50,
        crest_db=[8.0] * 50,
        nonspeech_loud=[0.2] * 50,
        speech_prob=[0.6] * 50,
    )
    chat = ChatFeatures(available=False, duration_s=50.0)

    mock_resp = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = (
        '{"verdict": "KEEP", "category": "clutch", "title": "Clutch 1v3 Luar Biasa", '
        '"hook_text": "Mustahil tapi terjadi!", "reason": "Pemain mengalahkan 3 musuh.", '
        '"confidence": 0.95, "flags": ["clutch"]}'
    )
    mock_resp.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    with (
        patch("clipforge.llm.client.settings.llm_base_url", "https://api.openai.com/v1"),
        patch("clipforge.llm.client.settings.llm_api_key", "sk-test"),
        patch("clipforge.llm.client.AsyncOpenAI", return_value=mock_client),
    ):
        res = await evaluate_candidate_scout(cand, tr, meta, audio, chat)
        assert res.verdict == "KEEP"
        assert res.category == "clutch"
        assert res.title == "Clutch 1v3 Luar Biasa"
        assert res.confidence == 0.95

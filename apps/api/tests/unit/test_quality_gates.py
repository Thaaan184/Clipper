"""Unit tests for pre-ASR heuristic quality gates."""

from clipforge.fusion.models import CandidateWindow
from clipforge.quality.gate import evaluate_quality_gate
from clipforge.signals.models import AudioFeatures, ChatFeatures


def test_talking_only_detected_gaming():
    # 30 seconds of high speech, low action
    duration = 30.0
    audio = AudioFeatures(
        duration_s=duration,
        loud_db=[-30.0] * 30,
        loud_surge=[0.05] * 30,  # low surge
        onset_density=[0.1] * 30,  # low onset
        hf_ratio=[0.2] * 30,
        crest_db=[5.0] * 30,
        nonspeech_loud=[0.05] * 30,
        speech_prob=[0.95] * 30,  # high speech
    )
    chat = ChatFeatures(
        available=True,
        duration_s=duration,
        chat_rate=[0.5] * 30,
        chat_hype=[0.02] * 30,  # low hype
        clip_intent=[0.0] * 30,
    )
    cand = CandidateWindow(
        id="cand_talk",
        rank=1,
        start_s=0.0,
        end_s=30.0,
        peak_s=15.0,
        duration_s=30.0,
        signal_score=0.4,
        final_score=0.4,
    )

    res = evaluate_quality_gate(cand, audio, chat, genre="gaming")
    assert not res.passed
    assert res.is_talking_only
    assert "talking_only" in res.flags


def test_intense_combat_passes_gaming():
    duration = 30.0
    audio = AudioFeatures(
        duration_s=duration,
        loud_db=[-10.0] * 30,
        loud_surge=[0.65] * 30,  # high surge
        onset_density=[2.5] * 30,  # high onset
        hf_ratio=[0.5] * 30,
        crest_db=[12.0] * 30,
        nonspeech_loud=[0.45] * 30,
        speech_prob=[0.50] * 30,
    )
    chat = ChatFeatures(
        available=True,
        duration_s=duration,
        chat_rate=[5.0] * 30,
        chat_hype=[0.80] * 30,
        clip_intent=[0.2] * 30,
    )
    cand = CandidateWindow(
        id="cand_combat",
        rank=1,
        start_s=0.0,
        end_s=30.0,
        peak_s=15.0,
        duration_s=30.0,
        signal_score=0.9,
        final_score=0.9,
    )

    res = evaluate_quality_gate(cand, audio, chat, genre="gaming")
    assert res.passed
    assert not res.is_talking_only
    assert "talking_only" not in res.flags


def test_podcast_talking_not_rejected():
    duration = 30.0
    audio = AudioFeatures(
        duration_s=duration,
        loud_db=[-25.0] * 30,
        loud_surge=[0.05] * 30,
        onset_density=[0.1] * 30,
        hf_ratio=[0.2] * 30,
        crest_db=[5.0] * 30,
        nonspeech_loud=[0.05] * 30,
        speech_prob=[0.95] * 30,
    )
    chat = ChatFeatures(available=False, duration_s=duration)
    cand = CandidateWindow(
        id="cand_pod",
        rank=1,
        start_s=0.0,
        end_s=30.0,
        peak_s=15.0,
        duration_s=30.0,
        signal_score=0.6,
        final_score=0.6,
    )

    # In podcast, talking is normal, should not be rejected by gaming talking-only rule
    res = evaluate_quality_gate(cand, audio, chat, genre="podcast")
    assert res.passed

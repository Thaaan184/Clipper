"""Candidate quality gates for filtering out talking-only and low-value segments."""

import numpy as np

from clipforge.fusion.models import CandidateWindow
from clipforge.quality.models import GateResult
from clipforge.signals.models import AudioFeatures, ChatFeatures


def evaluate_quality_gate(
    cand: CandidateWindow,
    audio_feats: AudioFeatures,
    chat_feats: ChatFeatures,
    genre: str = "gaming",
) -> GateResult:
    """
    Evaluate deterministic heuristic gates on a candidate window before targeted ASR and LLM.
    """
    start_idx = max(0, int(cand.start_s))
    end_idx = min(len(audio_feats.speech_prob), int(np.ceil(cand.end_s)))

    if end_idx <= start_idx:
        return GateResult(passed=True)

    sp_prob = audio_feats.speech_prob[start_idx:end_idx]
    surge = audio_feats.loud_surge[start_idx:end_idx]
    onsets = audio_feats.onset_density[start_idx:end_idx]

    mean_speech = float(np.mean(sp_prob)) if len(sp_prob) > 0 else 0.0
    max_surge = float(np.max(surge)) if len(surge) > 0 else 0.0
    mean_onset = float(np.mean(onsets)) if len(onsets) > 0 else 0.0

    mean_chat_hype = 0.0
    if chat_feats.available and len(chat_feats.chat_hype) > start_idx:
        c_hype_slice = chat_feats.chat_hype[start_idx:end_idx]
        if len(c_hype_slice) > 0:
            mean_chat_hype = float(np.mean(c_hype_slice))

    flags: list[str] = []
    passed = True
    reason = "Passed quality gate"
    penalty = 0.0
    is_talking = False

    # Gate 1: Talking-Only check (for gaming)
    if genre == "gaming":
        if mean_speech > 0.65 and max_surge < 0.20 and mean_onset < 0.50 and mean_chat_hype < 0.15:
            flags.append("talking_only")
            is_talking = True
            passed = False
            reason = "Continuous speech without gameplay combat action, loud events, or chat hype"
            penalty = 0.50

    # Gate 2: Short scream burst with dead air
    if max_surge > 0.80 and cand.duration_s < 20.0 and mean_onset < 0.20 and mean_speech < 0.20:
        flags.append("short_scream_burst")

    return GateResult(
        passed=passed,
        is_talking_only=is_talking,
        flags=flags,
        reason=reason,
        score_penalty=penalty,
    )

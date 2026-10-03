"""Unit tests for VAD."""

import numpy as np

from clipforge.signals.vad import compute_energy_vad, compute_vad


def test_vad_silence():
    sr = 16000
    audio = np.zeros(sr * 4, dtype=np.float32)

    speech_prob, segments = compute_vad(audio, sr=sr)
    assert len(speech_prob) == 4
    assert np.all(speech_prob == 0.0)
    assert len(segments) == 0


def test_energy_vad_speech_burst():
    sr = 16000
    audio = np.zeros(sr * 5, dtype=np.float32)

    # Insert a 1.5s speech-like burst from 1.0s to 2.5s
    t = np.linspace(0, 1.5, int(sr * 1.5), endpoint=False)
    burst = 0.5 * np.sin(2 * np.pi * 300 * t) + 0.3 * np.sin(2 * np.pi * 800 * t)
    audio[sr : sr + len(burst)] = burst.astype(np.float32)

    speech_prob, segments = compute_energy_vad(audio, sr=sr, threshold_db=-30.0)
    assert len(speech_prob) == 5
    assert speech_prob[1] > 0.5
    assert len(segments) >= 1
    assert any(seg.start_s <= 1.5 and seg.end_s >= 2.0 for seg in segments)

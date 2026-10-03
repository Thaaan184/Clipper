"""Unit tests for audio signal extraction."""

import numpy as np

from clipforge.signals.audio import extract_features_from_array


def test_audio_signals_silence():
    # 5 seconds of pure silence
    sr = 16000
    audio = np.zeros(sr * 5, dtype=np.float32)
    feats = extract_features_from_array(audio, sr=sr)

    assert len(feats.loud_db) == 5
    assert len(feats.onset_density) == 5
    assert len(feats.hf_ratio) == 5
    # Silence RMS in dB is around -180 dB
    assert all(db < -100.0 for db in feats.loud_db)
    assert all(od == 0.0 for od in feats.onset_density)


def test_audio_signals_loud_spike():
    sr = 16000
    # 10 seconds of background low noise, with a massive spike at second 5
    audio = np.random.uniform(-0.01, 0.01, sr * 10).astype(np.float32)

    # Inject sharp combat loud burst at second 5 (5.0s to 5.5s)
    spike_start = 5 * sr
    spike_end = spike_start + int(0.5 * sr)
    t = np.linspace(0, 0.5, spike_end - spike_start, endpoint=False)
    # High amplitude 3kHz tone (simulate gunshot / scream)
    audio[spike_start:spike_end] += 0.8 * np.sin(2 * np.pi * 3000 * t).astype(np.float32)

    feats = extract_features_from_array(audio, sr=sr)

    # Spike at index 5 should have higher loudness and higher loud_surge
    assert feats.loud_db[5] > feats.loud_db[1] + 20.0
    assert feats.loud_surge[5] > 10.0
    # High frequency energy ratio should be high at second 5
    assert feats.hf_ratio[5] > 0.50

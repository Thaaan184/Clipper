"""Unit tests for heatmap signal interpolation."""

from clipforge.signals.heatmap import extract_heatmap_features


def test_heatmap_unavailable():
    feats = extract_heatmap_features(None, duration_s=100.0)
    assert not feats.available
    assert len(feats.heatmap_curve) == 100
    assert all(v == 0.0 for v in feats.heatmap_curve)


def test_heatmap_interpolation():
    # Heatmap points at 10s (val 0.2) and 30s (val 1.0)
    raw = [
        {"start_time": 0.0, "end_time": 20.0, "value": 0.2},
        {"start_time": 20.0, "end_time": 40.0, "value": 1.0},
    ]
    feats = extract_heatmap_features(raw, duration_s=50.0)

    assert feats.available
    assert len(feats.heatmap_curve) == 50
    # Midpoint of first interval is 10.0 (val 0.2), second is 30.0 (val 1.0)
    # At second 20, interpolated value should be approx halfway ~0.6
    assert abs(feats.heatmap_curve[20] - 0.6) < 0.05
    assert abs(feats.heatmap_curve[30] - 1.0) < 0.05

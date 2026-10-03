"""Unit tests for fusion and candidate generation."""

import numpy as np

from clipforge.fusion.candidates import make_candidates, temporal_iou
from clipforge.fusion.fuse import fuse
from clipforge.fusion.models import CandidateGenerationConfig


def test_temporal_iou():
    # Identical
    assert temporal_iou(10.0, 30.0, 10.0, 30.0) == 1.0
    # No overlap
    assert temporal_iou(10.0, 20.0, 25.0, 35.0) == 0.0
    # Partial overlap: [10, 30] and [20, 40] -> intersection 10, union 30 -> 1/3
    assert abs(temporal_iou(10.0, 30.0, 20.0, 40.0) - (1.0 / 3.0)) < 1e-5


def test_fusion_dynamic_reweighting():
    # If chat is None, weights should redistribute to available signals
    signals: dict[str, np.ndarray | None] = {
        "loud_surge": np.array([0.1, 0.8, 0.2], dtype=np.float32),
        "onset_density": np.array([0.2, 0.7, 0.1], dtype=np.float32),
        "chat_rate": None,
    }
    weights = {"loud_surge": 0.5, "onset_density": 0.3, "chat_rate": 0.2}

    res = fuse(signals, weights)
    assert "chat_rate" not in res.used
    assert "loud_surge" in res.used
    assert "onset_density" in res.used
    assert len(res.score) == 3
    # Peak at index 1
    assert res.score[1] > res.score[0]


def test_make_candidates_duration_bounds():
    # Create a 200-second synthetic score curve with a strong peak at second 100
    score = np.zeros(200, dtype=np.float32)
    score[95:105] = 0.95

    cfg = CandidateGenerationConfig(
        min_duration_s=15.0,
        max_duration_s=60.0,
        pre_roll_s=8.0,
        post_roll_s=8.0,
    )
    cands = make_candidates(score, total_duration_s=200.0, cfg=cfg)

    assert len(cands) >= 1
    best = cands[0]
    # Check invariants
    assert best.start_s >= 0.0
    assert best.end_s <= 200.0
    assert best.end_s > best.start_s
    assert cfg.min_duration_s <= best.duration_s <= cfg.max_duration_s
    # Peak must be contained in candidate window
    assert best.start_s <= 100.0 <= best.end_s

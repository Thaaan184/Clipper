"""Unit tests for Golden Set evaluation metrics."""

from clipforge.eval.evaluate import evaluate_candidates_against_ground_truth


def test_evaluate_candidates_exact_hit():
    highlights = [
        {
            "start_s": 5340.0,
            "end_s": 5384.0,
            "label": "positive",
            "note": "Squad Wipe",
        }
    ]
    # Candidate exactly covering the highlight
    candidates = [
        {
            "rank": 1,
            "start_s": 5338.0,
            "end_s": 5386.0,
            "final_score": 0.95,
        }
    ]

    res = evaluate_candidates_against_ground_truth(candidates, highlights)
    assert res["total_ground_truth"] == 1
    assert res["hits_at_k"][3] == 1
    assert res["recall_at_k"][3] == 1.0
    assert res["mean_iou"] > 0.8
    assert res["matches"][0]["matched"] is True
    assert res["matches"][0]["matched_rank"] == 1


def test_evaluate_candidates_tbd_end():
    highlights = [
        {
            "start_s": 6503.0,
            "end_s": None,
            "label": "positive",
            "note": "Funny Aim Fail",
        }
    ]
    # Candidate covering start_s
    candidates = [
        {
            "rank": 2,
            "start_s": 6495.0,
            "end_s": 6535.0,
            "final_score": 0.85,
        }
    ]

    res = evaluate_candidates_against_ground_truth(candidates, highlights)
    assert res["total_ground_truth"] == 1
    assert res["hits_at_k"][3] == 1
    assert res["recall_at_k"][3] == 1.0
    assert res["matches"][0]["matched"] is True

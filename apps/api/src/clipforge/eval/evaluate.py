"""Evaluation runner for measuring candidate detector recall and precision against Golden Set."""

from typing import Any

from clipforge.fusion.candidates import temporal_iou


def evaluate_candidates_against_ground_truth(
    candidates: list[dict[str, Any]],
    highlights: list[dict[str, Any]],
    iou_thresh: float = 0.20,
    min_overlap_s: float = 10.0,
) -> dict[str, Any]:
    """
    Evaluate candidate windows against ground truth positive highlights.
    """
    total_positives = len(highlights)
    if total_positives == 0:
        return {
            "total_ground_truth": 0,
            "hits_at_k": {3: 0, 5: 0, 10: 0},
            "recall_at_k": {3: 0.0, 5: 0.0, 10: 0.0},
            "mean_iou": 0.0,
            "matches": [],
        }

    matches = []
    # Sort candidates by rank / final_score
    sorted_cands = sorted(
        candidates, key=lambda c: (c.get("rank", 999), -c.get("final_score", 0.0))
    )

    for h_idx, h in enumerate(highlights):
        h_start = float(h["start_s"])
        h_end = float(h["end_s"]) if h.get("end_s") is not None else None

        best_cand: dict[str, Any] | None = None
        best_iou = 0.0
        best_rank = 999
        is_hit = False

        for c in sorted_cands:
            c_start = float(c["start_s"])
            c_end = float(c["end_s"])
            c_rank = int(c.get("rank", 999))

            if h_end is not None:
                iou = temporal_iou(c_start, c_end, h_start, h_end)
                overlap = max(0.0, min(c_end, h_end) - max(c_start, h_start))
                hit = (iou >= iou_thresh) or (overlap >= min_overlap_s)
                if iou > best_iou:
                    best_iou = iou
            else:
                # TBD end: hit if candidate covers start_s within +- 15 seconds
                hit = (c_start - 15.0) <= h_start <= (c_end + 15.0)
                iou = 0.0

            if hit and (best_cand is None or c_rank < best_rank):
                is_hit = True
                best_cand = c
                best_rank = c_rank

        matches.append(
            {
                "highlight_idx": h_idx,
                "description": h.get("description", ""),
                "note": h.get("note", ""),
                "ground_truth": [h_start, h_end],
                "matched": is_hit,
                "matched_rank": best_rank if is_hit else None,
                "matched_window": [best_cand["start_s"], best_cand["end_s"]] if best_cand else None,
                "best_iou": round(best_iou, 3),
            }
        )

    # Compute Recall@K
    hits_at_k: dict[int, int] = {}
    recall_at_k: dict[int, float] = {}
    for k in (3, 5, 10):
        hits = sum(
            1
            for m in matches
            if m["matched"] and m["matched_rank"] is not None and m["matched_rank"] <= k
        )
        hits_at_k[k] = hits
        recall_at_k[k] = round(hits / total_positives, 3)

    mean_iou = round(float(sum(m["best_iou"] for m in matches) / max(1, total_positives)), 3)

    return {
        "total_ground_truth": total_positives,
        "hits_at_k": hits_at_k,
        "recall_at_k": recall_at_k,
        "mean_iou": mean_iou,
        "matches": matches,
    }

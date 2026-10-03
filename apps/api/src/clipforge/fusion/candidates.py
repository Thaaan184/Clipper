"""Candidate window generation via peak finding, region growing, and Non-Maximum Suppression."""

import uuid
from typing import Any

import numpy as np
import scipy.ndimage
import scipy.signal

from clipforge.fusion.models import CandidateGenerationConfig, CandidateWindow


def temporal_iou(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    intersection = max(0.0, min(end_a, end_b) - max(start_a, start_b))
    union = max(end_a, end_b) - min(start_a, start_b)
    if union <= 0.0:
        return 0.0
    return intersection / union


def nms(
    candidates: list[CandidateWindow],
    iou_thresh: float = 0.30,
    min_gap_s: float = 20.0,
    max_count: int = 30,
) -> list[CandidateWindow]:
    """
    Non-Maximum Suppression: suppress candidates that overlap with a higher-scoring candidate.
    """
    sorted_cands = sorted(candidates, key=lambda c: c.final_score, reverse=True)
    selected: list[CandidateWindow] = []

    for cand in sorted_cands:
        suppress = False
        for chosen in selected:
            # Check IoU
            iou = temporal_iou(cand.start_s, cand.end_s, chosen.start_s, chosen.end_s)
            if iou > iou_thresh:
                suppress = True
                break
            # Check peak distance
            if abs(cand.peak_s - chosen.peak_s) < min_gap_s:
                suppress = True
                break

        if not suppress:
            selected.append(cand)
            if len(selected) >= max_count:
                break

    # Sort remaining by timestamp for consistent display, assign ranks by score
    scored_ranks = sorted(selected, key=lambda c: c.final_score, reverse=True)
    for rank_idx, cand in enumerate(scored_ranks, start=1):
        cand.rank = rank_idx

    return selected


def grow_region(
    score: np.ndarray,
    peak_idx: int,
    alpha: float = 0.50,
    max_pre_s: float = 40.0,
    max_post_s: float = 40.0,
    hop_s: float = 1.0,
) -> tuple[float, float]:
    """Expand region around peak until score falls below alpha * peak_score."""
    peak_val = score[peak_idx]
    threshold = alpha * peak_val

    lo = peak_idx
    while lo > 0 and score[lo - 1] >= threshold and (peak_idx - (lo - 1)) * hop_s <= max_pre_s:
        lo -= 1

    hi = peak_idx
    max_len = len(score)
    while (
        hi < max_len - 1
        and score[hi + 1] >= threshold
        and ((hi + 1) - peak_idx) * hop_s <= max_post_s
    ):
        hi += 1

    return lo * hop_s, hi * hop_s


def apply_roll_and_clamp(
    lo_s: float,
    hi_s: float,
    peak_s: float,
    total_duration_s: float,
    cfg: CandidateGenerationConfig,
) -> tuple[float, float]:
    """Apply pre/post-roll and clamp to [min_dur, max_dur]."""
    start_s = max(0.0, lo_s - cfg.pre_roll_s)
    end_s = min(total_duration_s, hi_s + cfg.post_roll_s)

    duration = end_s - start_s

    # If too short, expand setup first
    if duration < cfg.min_duration_s:
        needed = cfg.min_duration_s - duration
        # Give 70% to setup (pre), 30% to post
        pre_add = needed * 0.7
        post_add = needed * 0.3

        start_s = max(0.0, start_s - pre_add)
        end_s = min(total_duration_s, end_s + post_add)

        # If still short because bounded by 0 or total_duration
        if end_s - start_s < cfg.min_duration_s:
            if start_s == 0.0:
                end_s = min(total_duration_s, start_s + cfg.min_duration_s)
            elif end_s == total_duration_s:
                start_s = max(0.0, end_s - cfg.min_duration_s)

    # If too long, clamp around peak with 60:40 pre/post ratio
    elif duration > cfg.max_duration_s:
        max_pre = cfg.max_duration_s * 0.60
        max_post = cfg.max_duration_s * 0.40

        target_start = max(0.0, peak_s - max_pre)
        target_end = min(total_duration_s, peak_s + max_post)

        if target_end - target_start < cfg.max_duration_s:
            if target_start == 0.0:
                target_end = min(total_duration_s, cfg.max_duration_s)
            elif target_end == total_duration_s:
                target_start = max(0.0, total_duration_s - cfg.max_duration_s)

        start_s = target_start
        end_s = target_end

    return round(start_s, 2), round(end_s, 2)


def make_candidates(
    score: np.ndarray,
    total_duration_s: float,
    cfg: CandidateGenerationConfig,
    hop_s: float = 1.0,
    per_signal_norm: dict[str, np.ndarray] | None = None,
) -> list[CandidateWindow]:
    """
    Generate candidate windows from fused score curve.
    """
    if len(score) == 0:
        return []

    # 1. Gaussian smoothing
    sigma = max(0.5, cfg.sigma_s / hop_s)
    smoothed = scipy.ndimage.gaussian_filter1d(score, sigma=sigma)

    # 2. Dynamic peak height: max(abs_floor, percentile-90)
    p90 = float(np.percentile(smoothed, 90)) if len(smoothed) > 10 else cfg.abs_floor
    height = max(cfg.abs_floor, p90)

    distance_bins = max(1, int(round(cfg.min_gap_s / hop_s)))

    peaks, properties = scipy.signal.find_peaks(
        smoothed,
        height=height,
        prominence=cfg.prominence,
        distance=distance_bins,
    )

    # Fallback if no peaks meet strict criteria: lower height to abs_floor
    if len(peaks) == 0 and height > cfg.abs_floor:
        peaks, properties = scipy.signal.find_peaks(
            smoothed,
            height=cfg.abs_floor,
            prominence=cfg.prominence * 0.7,
            distance=distance_bins,
        )

    candidates: list[CandidateWindow] = []

    for peak_idx in peaks:
        peak_s = peak_idx * hop_s
        peak_val = float(smoothed[peak_idx])

        lo_s, hi_s = grow_region(
            score=smoothed,
            peak_idx=peak_idx,
            alpha=cfg.alpha,
            hop_s=hop_s,
        )

        start_s, end_s = apply_roll_and_clamp(
            lo_s=lo_s,
            hi_s=hi_s,
            peak_s=peak_s,
            total_duration_s=total_duration_s,
            cfg=cfg,
        )

        # Collect evidence signals active around peak
        evidence: dict[str, Any] = {
            "peak_score": round(peak_val, 3),
            "smoothed_score": round(float(smoothed[peak_idx]), 3),
            "signals": {},
        }
        if per_signal_norm:
            for s_name, s_arr in per_signal_norm.items():
                if peak_idx < len(s_arr):
                    evidence["signals"][s_name] = round(float(s_arr[peak_idx]), 3)

        cand_id = f"cand_{uuid.uuid4().hex[:8]}"
        candidates.append(
            CandidateWindow(
                id=cand_id,
                rank=1,
                start_s=start_s,
                end_s=end_s,
                peak_s=round(peak_s, 2),
                duration_s=round(end_s - start_s, 2),
                signal_score=round(peak_val, 3),
                final_score=round(peak_val, 3),
                category="gameplay_highlight",
                title=f"Highlight at {int(start_s // 60):02d}:{int(start_s % 60):02d}",
                evidence=evidence,
            )
        )

    # 3. Apply NMS
    return nms(
        candidates,
        iou_thresh=cfg.nms_iou_threshold,
        min_gap_s=cfg.min_gap_s,
        max_count=cfg.max_candidates,
    )

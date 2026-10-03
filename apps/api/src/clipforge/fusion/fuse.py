"""Multi-modal signal fusion with dynamic reweighting and cross-modality agreement bonus."""

import numpy as np
import scipy.ndimage

from clipforge.fusion.models import FuseResult
from clipforge.fusion.normalize import robust_z, to_unit

DEFAULT_MODALITY_MAP = {
    "audio": {"loud_surge", "onset_density", "nonspeech_loud", "hf_ratio"},
    "chat": {"chat_rate", "chat_hype", "clip_intent"},
    "heatmap": {"heatmap"},
    "visual": {"visual_motion"},
}


def agreement_mask(
    norm_signals: dict[str, np.ndarray],
    modalities: dict[str, set[str]],
    threshold: float = 0.6,
    min_modalities: int = 3,
    window_s: float = 5.0,
) -> np.ndarray:
    """
    Calculate cross-modality agreement mask.
    Returns 1.0 at times where >= min_modalities have active signals inside +- window_s.
    """
    if not norm_signals:
        return np.zeros(0, dtype=np.float32)

    sample_len = len(next(iter(norm_signals.values())))
    if sample_len == 0:
        return np.zeros(0, dtype=np.float32)

    mod_active_curves: list[np.ndarray] = []

    win_size = int(round(2 * window_s + 1))
    if win_size % 2 == 0:
        win_size += 1

    for _mod_name, sig_names in modalities.items():
        # Check if any signal of this modality is active
        mod_signals = [norm_signals[k] for k in sig_names if k in norm_signals]
        if not mod_signals:
            continue

        # Active if any signal exceeds threshold
        stacked = np.stack(mod_signals, axis=0)
        max_sig = np.max(stacked, axis=0)
        active_binary = (max_sig >= threshold).astype(np.float32)

        # Dilate across +- window_s
        dilated = scipy.ndimage.maximum_filter1d(active_binary, size=win_size, mode="constant")
        mod_active_curves.append(dilated)

    if len(mod_active_curves) < min_modalities:
        return np.zeros(sample_len, dtype=np.float32)

    total_active_modalities = np.sum(np.stack(mod_active_curves, axis=0), axis=0)
    return np.asarray((total_active_modalities >= min_modalities).astype(np.float32))


def fuse(
    signals: dict[str, np.ndarray | None],
    weights: dict[str, float],
    agree_thr: float = 0.6,
    agree_min: int = 3,
    agree_bonus: float = 0.10,
    agree_win_s: float = 5.0,
    z_lo: float = 0.5,
    z_hi: float = 4.0,
    modality_map: dict[str, set[str]] | None = None,
) -> FuseResult:
    """
    Fuse available multi-modal signals into a single score array in [0.0, 1.0].
    """
    avail = {
        k: v
        for k, v in signals.items()
        if v is not None and len(v) > 0 and weights.get(k, 0.0) > 0.0
    }
    if not avail:
        return FuseResult(
            score=np.zeros(0, dtype=np.float32),
            used=[],
            per_signal={},
            agreement_bonus=np.zeros(0, dtype=np.float32),
        )

    # Renormalize weights across currently available signals
    wsum = sum(weights[k] for k in avail)
    if wsum <= 0:
        wsum = 1.0

    norm: dict[str, np.ndarray] = {
        k: to_unit(robust_z(v), z_lo=z_lo, z_hi=z_hi) for k, v in avail.items()
    }

    # Weighted baseline score
    sample_len = len(next(iter(norm.values())))
    S = np.zeros(sample_len, dtype=np.float32)
    for k, norm_arr in norm.items():
        w_norm = weights[k] / wsum
        S += (w_norm * norm_arr).astype(np.float32)

    # Cross-modality agreement bonus
    mods = modality_map if modality_map is not None else DEFAULT_MODALITY_MAP
    # Count how many modalities are actually available
    active_mods_count = sum(1 for m_sigs in mods.values() if any(s in avail for s in m_sigs))
    effective_min_mods = min(agree_min, active_mods_count)

    bonus_mask = agreement_mask(
        norm_signals=norm,
        modalities=mods,
        threshold=agree_thr,
        min_modalities=effective_min_mods,
        window_s=agree_win_s,
    )
    agreement_bonus_arr = bonus_mask * agree_bonus

    final_score = np.clip(S + agreement_bonus_arr, 0.0, 1.0)

    return FuseResult(
        score=final_score,
        used=sorted(avail.keys()),
        per_signal=norm,
        agreement_bonus=agreement_bonus_arr,
    )

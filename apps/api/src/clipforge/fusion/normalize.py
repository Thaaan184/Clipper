"""Pure normalization functions for signal arrays."""

import numpy as np


def robust_z(x: np.ndarray) -> np.ndarray:
    """
    Compute robust z-score: (x - median) / (1.4826 * MAD + 1e-9).
    """
    if len(x) == 0:
        return np.zeros_like(x)

    med = np.nanmedian(x)
    mad = np.nanmedian(np.abs(x - med))
    scale = 1.4826 * mad + 1e-9
    return np.asarray((x - med) / scale)


def to_unit(z: np.ndarray, z_lo: float = 0.5, z_hi: float = 4.0) -> np.ndarray:
    """
    Map robust z-scores to [0.0, 1.0] interval using z_lo and z_hi thresholds.
    """
    if z_hi <= z_lo:
        return np.asarray(np.clip(z, 0.0, 1.0))
    return np.asarray(np.clip((z - z_lo) / (z_hi - z_lo), 0.0, 1.0))

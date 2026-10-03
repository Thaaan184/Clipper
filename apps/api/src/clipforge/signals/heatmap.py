"""Extract and interpolate YouTube 'most replayed' heatmap onto 1-second time grid."""

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from clipforge.signals.models import HeatmapFeatures


def extract_heatmap_features(
    heatmap_data: list[dict[str, Any]] | Path | None,
    duration_s: float,
) -> HeatmapFeatures:
    """
    Interpolate YouTube heatmap markers into a uniform 1-second grid.
    """
    num_secs = max(1, int(math.ceil(duration_s)))

    if heatmap_data is None:
        return HeatmapFeatures(
            available=False,
            duration_s=duration_s,
            heatmap_curve=list(np.zeros(num_secs, dtype=float)),
        )

    raw_items: list[dict[str, Any]] = []
    if isinstance(heatmap_data, Path):
        if not heatmap_data.exists():
            return HeatmapFeatures(
                available=False,
                duration_s=duration_s,
                heatmap_curve=list(np.zeros(num_secs, dtype=float)),
            )
        try:
            raw_items = json.loads(heatmap_data.read_text(encoding="utf-8"))
        except Exception:
            raw_items = []
    elif isinstance(heatmap_data, list):
        raw_items = heatmap_data

    if not raw_items:
        return HeatmapFeatures(
            available=False,
            duration_s=duration_s,
            heatmap_curve=list(np.zeros(num_secs, dtype=float)),
        )

    # Extract sample midpoints and values
    t_points = []
    v_points = []

    for item in raw_items:
        start_t = float(item.get("start_time", 0.0))
        end_t = float(item.get("end_time", start_t))
        val = float(item.get("value", 0.0))
        mid_t = (start_t + end_t) / 2.0
        t_points.append(mid_t)
        v_points.append(val)

    if not t_points:
        return HeatmapFeatures(
            available=False,
            duration_s=duration_s,
            heatmap_curve=list(np.zeros(num_secs, dtype=float)),
        )

    # Sort by time
    sorted_pairs = sorted(zip(t_points, v_points, strict=False), key=lambda x: x[0])
    t_arr = np.array([p[0] for p in sorted_pairs], dtype=np.float32)
    v_arr = np.array([p[1] for p in sorted_pairs], dtype=np.float32)

    # Linear interpolation onto 1-second grid [0, 1, ..., num_secs-1]
    grid_t = np.arange(num_secs, dtype=np.float32)
    interpolated = np.interp(grid_t, t_arr, v_arr, left=float(v_arr[0]), right=float(v_arr[-1]))

    return HeatmapFeatures(
        available=True,
        duration_s=duration_s,
        heatmap_curve=[float(x) for x in interpolated],
    )

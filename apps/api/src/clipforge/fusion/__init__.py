"""Fusion subsystem for multi-modal signals."""

from clipforge.fusion.candidates import make_candidates, nms, temporal_iou
from clipforge.fusion.fuse import agreement_mask, fuse
from clipforge.fusion.models import (
    AgreementConfig,
    CandidateGenerationConfig,
    CandidateWindow,
    FuseConfig,
    FuseResult,
)
from clipforge.fusion.normalize import robust_z, to_unit
from clipforge.fusion.presets import load_preset
from clipforge.fusion.snap import refine_boundaries, snap_to_silence

__all__ = [
    "AgreementConfig",
    "CandidateGenerationConfig",
    "CandidateWindow",
    "FuseConfig",
    "FuseResult",
    "agreement_mask",
    "fuse",
    "load_preset",
    "make_candidates",
    "nms",
    "refine_boundaries",
    "robust_z",
    "snap_to_silence",
    "temporal_iou",
    "to_unit",
]

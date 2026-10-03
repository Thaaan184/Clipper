"""Signals subsystem for ClipForge v2."""

from clipforge.signals.audio import extract_audio_features
from clipforge.signals.chat import extract_chat_features
from clipforge.signals.heatmap import extract_heatmap_features
from clipforge.signals.models import (
    AllSignals,
    AudioFeatures,
    ChatFeatures,
    HeatmapFeatures,
    SpeechSegment,
)
from clipforge.signals.vad import compute_energy_vad, compute_vad

__all__ = [
    "AllSignals",
    "AudioFeatures",
    "ChatFeatures",
    "HeatmapFeatures",
    "SpeechSegment",
    "compute_energy_vad",
    "compute_vad",
    "extract_audio_features",
    "extract_chat_features",
    "extract_heatmap_features",
]

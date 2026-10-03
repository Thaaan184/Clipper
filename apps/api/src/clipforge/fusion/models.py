"""Data models for signal fusion and candidate generation."""

from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import BaseModel, Field


class AgreementConfig(BaseModel):
    min_modalities: int = 3
    threshold: float = 0.6
    bonus: float = 0.10
    window_s: float = 5.0


class CandidateGenerationConfig(BaseModel):
    sigma_s: float = 2.0
    min_gap_s: float = 20.0
    prominence: float = 0.15
    abs_floor: float = 0.30
    alpha: float = 0.50
    pre_roll_s: float = 8.0
    post_roll_s: float = 8.0
    min_duration_s: float = 15.0
    max_duration_s: float = 60.0
    target_duration_s: float = 35.0
    nms_iou_threshold: float = 0.30
    max_candidates: int = 30


class FuseConfig(BaseModel):
    name: str = "gaming"
    description: str = ""
    weights: dict[str, float] = Field(default_factory=dict)
    agreement: AgreementConfig = Field(default_factory=AgreementConfig)
    candidate_generation: CandidateGenerationConfig = Field(
        default_factory=CandidateGenerationConfig
    )


@dataclass
class FuseResult:
    score: np.ndarray
    used: list[str]
    per_signal: dict[str, np.ndarray]
    agreement_bonus: np.ndarray


class CandidateWindow(BaseModel):
    id: str
    rank: int = 1
    start_s: float
    end_s: float
    peak_s: float
    duration_s: float
    signal_score: float
    llm_score: float | None = None
    final_score: float
    category: str = "highlight"
    title: str = ""
    hook_text: str = ""
    reason: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    flags: list[str] = Field(default_factory=list)
    status: str = "proposed"
    user_start_s: float | None = None
    user_end_s: float | None = None

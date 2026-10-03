"""Models for timeline visualization and candidate review."""

from typing import Any

from pydantic import BaseModel, Field

from clipforge.fusion.models import CandidateWindow


class TimelineCurve(BaseModel):
    name: str
    available: bool = True
    color: str | None = None
    values: list[float] = Field(default_factory=list)


class TimelineResponse(BaseModel):
    job_id: str
    duration_s: float
    hop_s: float = 1.0
    signals: dict[str, list[float]] = Field(default_factory=dict)
    candidates: list[CandidateWindow] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidatesResponse(BaseModel):
    job_id: str
    total_candidates: int
    candidates: list[CandidateWindow]

"""Job models, enums, and schemas."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    RENDERING = "rendering"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageName(StrEnum):
    VALIDATE = "validate"
    FETCH_SIGNALS = "fetch_signals"
    ANALYZE_SIGNALS = "analyze_signals"
    FUSE_CANDIDATES = "fuse_candidates"
    LIGHT_VISUAL = "light_visual"
    TARGETED_ASR = "targeted_asr"
    SCOUT_RERANK = "scout_rerank"
    REFINE_BOUNDARIES = "refine_boundaries"
    RENDER_CLIPS = "render_clips"


class JobCreateRequest(BaseModel):
    source_url: str = Field(..., description="YouTube URL")
    genre: str = Field(default="gaming", description="Content genre")
    language: str = Field(default="id", description="Language code: id, en, auto")
    clip_count: int = Field(default=5, ge=1, le=10, description="Target clip count")
    min_duration_s: float = Field(default=15.0, ge=10.0, description="Min clip duration")
    max_duration_s: float = Field(default=60.0, le=180.0, description="Max clip duration")
    reframe_mode: str = Field(default="blur", description="blur, center, stacked")
    subtitle_style: str = Field(default="classic_white", description="Subtitle visual preset")


class JobResponse(BaseModel):
    id: str
    source_url: str
    video_id: str | None = None
    title: str | None = None
    duration_s: float | None = None
    genre: str
    language: str
    status: JobStatus
    stage: str | None = None
    progress: float = 0.0
    error_code: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str
    finished_at: str | None = None


class JobEvent(BaseModel):
    id: int | None = None
    job_id: str
    ts: str
    type: str
    payload: dict[str, Any]

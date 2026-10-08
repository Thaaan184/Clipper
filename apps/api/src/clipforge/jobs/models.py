"""Job models, enums, and schemas."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


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
    manual: bool = Field(default=False, description="Manual clip mode flag")
    start_time: str | float | None = Field(default=None, description="Start timestamp for manual clip")
    end_time: str | float | None = Field(default=None, description="End timestamp for manual clip")
    params: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def unpack_nested_params(cls, data: Any) -> Any:
        if isinstance(data, dict):
            p = data.get("params")
            if isinstance(p, dict):
                for k in (
                    "clip_count",
                    "min_duration_s",
                    "max_duration_s",
                    "reframe_mode",
                    "subtitle_style",
                    "manual",
                    "start_time",
                    "end_time",
                ):
                    if k in p and (k not in data or data[k] is None):
                        data[k] = p[k]
        return data


class ManualClipCreateRequest(BaseModel):
    source_url: str = Field(..., description="YouTube video URL")
    start_time: str | float = Field(..., description="Start timestamp (e.g. '12:35' or seconds)")
    end_time: str | float = Field(..., description="End timestamp (e.g. '14:20' or seconds)")
    title: str | None = Field(default=None, description="Optional custom title")
    reframe_mode: str = Field(default="blur", description="blur, center, stacked")
    subtitle_style: str = Field(default="none", description="Subtitle visual preset")
    language: str = Field(default="id", description="Language code")


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

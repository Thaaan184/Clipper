"""Data models for ingest subsystem."""

from typing import Any

from pydantic import BaseModel, Field


class VideoMetadata(BaseModel):
    video_id: str
    canonical_url: str
    title: str
    duration_s: float
    is_live: bool = False
    live_status: str | None = None
    channel: str | None = None
    channel_id: str | None = None
    upload_date: str | None = None
    has_chat: bool = False
    has_subtitles: bool = False
    has_heatmap: bool = False
    formats_summary: list[dict[str, Any]] = Field(default_factory=list)
    heatmap_raw: list[dict[str, Any]] = Field(default_factory=list)


class IngestResult(BaseModel):
    metadata: VideoMetadata
    audio_path: str
    chat_path: str | None = None
    heatmap_path: str | None = None
    disk_used_bytes: int = 0

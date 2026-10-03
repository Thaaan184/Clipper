from pydantic import BaseModel, field_validator
from typing import Optional
import re


class ScanRequest(BaseModel):
    url: str
    clip_count: int = 5
    duration_target: str = "30-60"  # "15-30" | "30-60" | "60-90"
    content_type: str = "auto"      # "auto" | "gaming" | "podcast" | "education" | "comedy" | "motivation"
    subtitle_lang: str = "id"       # "id" | "en" | "none"
    layout: str = "blur"            # "blur" | "center" | "stacked"

    @field_validator("url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        pattern = r"^(https?://)?((www|m)\.)?(youtube\.com/(watch\?v=|live/|shorts/|embed/)|youtu\.be/)[\w\-]{11}"
        if not re.search(pattern, v, re.IGNORECASE):
            raise ValueError("Bukan link YouTube valid")
        return v

    @field_validator("clip_count")
    @classmethod
    def validate_clip_count(cls, v: int) -> int:
        if not 1 <= v <= 10:
            raise ValueError("clip_count harus antara 1 dan 10")
        return v


class ScanResponse(BaseModel):
    job_id: str
    video_id: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    phase: Optional[str] = None
    progress: int = 0
    message: Optional[str] = None
    error_msg: Optional[str] = None


class ClipBrief(BaseModel):
    start_time: float
    end_time: float
    hook_title: str
    score: int
    reason: str
    caption: str
    hashtags: list[str]
    content_type: str = "general"


class ClipInfo(BaseModel):
    id: str
    video_id: str
    clip_index: int
    start_time: float
    end_time: float
    duration: float
    hook_title: Optional[str]
    score: int
    caption: Optional[str]
    hashtags: Optional[list[str]]
    content_type: Optional[str]
    layout: str
    subtitle_lang: Optional[str] = "id"
    status: str
    error_msg: Optional[str]
    file_path: Optional[str]
    transcript: Optional[str] = None
    subtitles_json: Optional[str] = None


class VideoInfo(BaseModel):
    id: str
    url: str
    title: Optional[str]
    duration: Optional[int]
    thumbnail: Optional[str]
    channel: Optional[str]
    status: str
    clips: list[ClipInfo] = []


class RescanRequest(BaseModel):
    clip_count: int = 5
    duration_target: str = "30-60"
    content_type: str = "auto"
    subtitle_lang: str = "id"
    layout: str = "blur"


class RenderRequest(BaseModel):
    layout: Optional[str] = "blur"
    subtitle_lang: Optional[str] = "id"
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    hook_title: Optional[str] = None
    custom_subtitles: Optional[list[dict]] = None
    custom_transcript: Optional[str] = None


class SSEEvent(BaseModel):
    event: str  # "progress" | "done" | "error"
    job_id: str
    phase: Optional[str] = None
    progress: int = 0
    message: Optional[str] = None
    clips: Optional[list[ClipInfo]] = None
    error: Optional[str] = None

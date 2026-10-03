"""ClipForge v2 configuration."""

from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CF_",
        env_file=".env",
        extra="ignore",
    )

    data_dir: Path = Field(default=Path("./data"), description="Root directory for job artifacts")
    db_path: Path = Field(default=Path("./data/clipforge.db"), description="SQLite database path")
    bind: str = Field(default="127.0.0.1", description="Listen address")
    port: int = Field(default=8000, description="Listen port")
    api_token: str | None = Field(default=None, description="Optional Bearer token")
    cors_origins: list[str] | str = Field(
        default=["http://localhost:5173"], description="Allowed CORS origins"
    )
    allowed_hosts: list[str] | str = Field(
        default=["youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"],
        description="Allowed media source hostnames",
    )

    @field_validator("allowed_hosts", "cors_origins", mode="after")
    @classmethod
    def parse_str_list(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                import json

                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(item) for item in parsed]
                except Exception:
                    pass
            return [part.strip() for part in v.split(",") if part.strip()]
        if isinstance(v, list):
            return [str(item) for item in v]
        return []
    max_vod_seconds: int = Field(
        default=28800, description="Maximum VOD length in seconds (8 hours)"
    )
    max_concurrent_jobs: int = Field(default=1, description="Max concurrent jobs running")
    max_concurrent_ffmpeg: int = Field(default=2, description="Max concurrent FFmpeg processes")

    whisper_model: str = Field(default="base", description="Whisper model name/path")
    whisper_device: str = Field(default="auto", description="auto | cpu | cuda")
    whisper_compute: str = Field(default="auto", description="int8 | float16 | auto")

    llm_base_url: str | None = Field(default=None, description="OpenAI-compatible base URL")
    llm_api_key: str | None = Field(default=None, description="LLM API key")
    llm_model: str | None = Field(default=None, description="LLM model name")
    llm_vision_model: str | None = Field(default=None, description="Optional vision model")

    ffmpeg_encoder: str = Field(
        default="libx264", description="Video encoder (libx264, h264_nvenc, auto)"
    )
    ttl_hours: int = Field(default=168, description="Data retention in hours (default 7 days)")
    cookies_file: Path | None = Field(default=None, description="Path to cookies.txt")
    preset_dir: Path = Field(default=Path("./presets"), description="Path to presets directory")


settings = Settings()

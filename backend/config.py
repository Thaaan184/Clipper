from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    llm_api_base: str = "http://100.96.207.8:20128/v1"
    llm_api_key: str = "sk-ec8b765ea71ee2fe-gblh28-e9935933"
    llm_model: str = "ag/gemini-3.8-flash-medium"

    # App
    port: int = 8080
    data_dir: Path = Path("./data")
    max_video_duration: int = 10800  # 3 hours
    max_concurrent_renders: int = 3
    max_pending_jobs: int = 5
    max_disk_gb: int = 10

    # Whisper
    whisper_model: str = "large-v3"
    whisper_device: str = "cpu"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # Rate limit
    rate_limit_scans_per_hour: int = 5

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "clipforge.db"


settings = Settings()

# Ensure data dirs exist
settings.raw_dir.mkdir(parents=True, exist_ok=True)
settings.processed_dir.mkdir(parents=True, exist_ok=True)

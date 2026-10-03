"""Data models for targeted ASR transcription."""

from pydantic import BaseModel, Field


class WordTimestamp(BaseModel):
    idx: int
    start_s: float
    end_s: float
    text: str
    confidence: float = 1.0


class CandidateTranscript(BaseModel):
    candidate_id: str
    text: str = ""
    language: str = "id"
    words: list[WordTimestamp] = Field(default_factory=list)

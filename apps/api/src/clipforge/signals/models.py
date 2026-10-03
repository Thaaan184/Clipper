"""Data models for signals extracted from audio, chat, and heatmap."""

from pydantic import BaseModel, Field


class SpeechSegment(BaseModel):
    start_s: float
    end_s: float
    confidence: float = 1.0


class AudioFeatures(BaseModel):
    duration_s: float
    loud_db: list[float]
    loud_surge: list[float]
    onset_density: list[float]
    hf_ratio: list[float]
    crest_db: list[float]
    nonspeech_loud: list[float]
    speech_prob: list[float]
    speech_segments: list[SpeechSegment] = Field(default_factory=list)


class ChatFeatures(BaseModel):
    available: bool = False
    duration_s: float = 0.0
    chat_rate: list[float] = Field(default_factory=list)
    chat_hype: list[float] = Field(default_factory=list)
    clip_intent: list[float] = Field(default_factory=list)
    total_messages: int = 0


class HeatmapFeatures(BaseModel):
    available: bool = False
    duration_s: float = 0.0
    heatmap_curve: list[float] = Field(default_factory=list)


class AllSignals(BaseModel):
    duration_s: float
    audio: AudioFeatures
    chat: ChatFeatures
    heatmap: HeatmapFeatures

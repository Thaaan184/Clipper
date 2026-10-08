"""Data models for subtitle generation and styling."""

from pydantic import BaseModel


class SubtitleWord(BaseModel):
    idx: int
    start_s: float
    end_s: float
    text: str
    confidence: float = 1.0
    speaker: str = "speaker_1"
    pos_y: int | None = None


class SubtitleChunk(BaseModel):
    words: list[SubtitleWord]
    start_s: float
    end_s: float
    speaker: str = "speaker_1"
    pos_y: int | None = None


class SubtitleStylePreset(BaseModel):
    name: str = "classic_white"
    font_name: str = "Liberation Sans"
    font_size: int = 48
    primary_color: str = "&H00FFFFFF&"
    active_color: str = "&H00008CFF&"
    outline_color: str = "&H00000000&"
    back_color: str = "&H00000000&"
    outline: int = 3
    shadow: int = 2
    bold: int = 1
    italic: int = 0
    alignment: int = 2
    margin_v: int = 240
    uppercase: bool = False

"""Data models for LLM Scout evaluation."""

from typing import Literal

from pydantic import BaseModel, Field


class ScoutVerdict(BaseModel):
    verdict: Literal["KEEP", "REJECT"] = "KEEP"
    category: str = "gameplay_highlight"
    title: str = "Momen Seru"
    hook_text: str = ""
    reason: str = ""
    confidence: float = 0.8
    flags: list[str] = Field(default_factory=list)

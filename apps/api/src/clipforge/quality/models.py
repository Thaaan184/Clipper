"""Data models for candidate quality gates."""

from pydantic import BaseModel, Field


class GateResult(BaseModel):
    passed: bool = True
    is_talking_only: bool = False
    flags: list[str] = Field(default_factory=list)
    reason: str = ""
    score_penalty: float = 0.0

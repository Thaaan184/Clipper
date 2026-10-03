"""LLM subsystem for candidate scoring, hook generation, and title generation."""

from clipforge.llm.client import evaluate_candidate_scout
from clipforge.llm.models import ScoutVerdict

__all__ = ["evaluate_candidate_scout", "ScoutVerdict"]

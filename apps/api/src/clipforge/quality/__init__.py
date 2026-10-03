"""Quality filtering subsystem for candidate validation."""

from clipforge.quality.gate import evaluate_quality_gate
from clipforge.quality.models import GateResult

__all__ = ["evaluate_quality_gate", "GateResult"]

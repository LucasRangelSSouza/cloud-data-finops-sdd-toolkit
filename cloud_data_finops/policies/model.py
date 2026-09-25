"""Finding model shared by every rule.

A finding keeps five things apart: what the telemetry showed, how any derived
number was calculated, what to do next, what the impact estimate is (or why
there is none), and how confident the rule is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

BYTES_PER_TB = 10**12
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
CONFIDENCE_LEVELS = ("high", "medium", "low")


@dataclass(frozen=True)
class Calculation:
    inputs: dict[str, Any]
    formula: str
    result: dict[str, Any]
    units: dict[str, str]
    assumptions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "inputs": dict(self.inputs),
            "formula": self.formula,
            "result": dict(self.result),
            "units": dict(self.units),
            "assumptions": list(self.assumptions),
        }


@dataclass(frozen=True)
class EstimatedImpact:
    """An estimate is present only when its value, unit, and basis are all known."""

    value: float | None
    unit: str | None
    basis: str

    @classmethod
    def not_estimated(cls, reason: str) -> EstimatedImpact:
        return cls(value=None, unit=None, basis=reason)

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "unit": self.unit, "basis": self.basis}


@dataclass(frozen=True)
class Finding:
    rule_id: str
    provider: str
    title: str
    subject: str
    priority: str
    evidence_source: str
    observed_evidence: dict[str, Any]
    calculation: Calculation
    recommendation: str
    action: str
    estimated_impact: EstimatedImpact
    confidence: str
    related_rules: tuple[str, ...] = field(default=())
    # Magnitude used only to order findings of the same rule; not serialized.
    weight: float = field(default=0.0, compare=False)

    def __post_init__(self) -> None:
        if self.priority not in PRIORITY_ORDER:
            raise ValueError(f"unsupported priority for {self.rule_id}")
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"unsupported confidence for {self.rule_id}")

    @property
    def sort_key(self) -> tuple[int, str, float, str]:
        return (PRIORITY_ORDER[self.priority], self.rule_id, -self.weight, self.subject)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "provider": self.provider,
            "title": self.title,
            "subject": self.subject,
            "priority": self.priority,
            "evidence_source": self.evidence_source,
            "observed_evidence": dict(self.observed_evidence),
            "calculation": self.calculation.to_dict(),
            "recommendation": self.recommendation,
            "action": self.action,
            "estimated_impact": self.estimated_impact.to_dict(),
            "confidence": self.confidence,
            "related_rules": list(self.related_rules),
        }


def terabytes(byte_count: float) -> float:
    return round(byte_count / BYTES_PER_TB, 3)


def ratio(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 4)

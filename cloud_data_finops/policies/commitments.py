"""Commitment and discount observations.

The rule reports steady on-demand usage with low commitment coverage. It never
recommends a purchase unless the evidence is complete: enough monthly history,
a discount rate approved in the specification, and a usage forecast confirmed
by the workload owner.
"""

from __future__ import annotations

from statistics import mean, pstdev
from typing import Any

from .model import Calculation, EstimatedImpact, Finding


def missing_commitment_evidence(history_months: int, service_assumptions: dict[str, Any], required_months: float) -> list[str]:
    missing = []
    if history_months < required_months:
        missing.append(f"{int(required_months)} months of usage history")
    rate = service_assumptions.get("discount_rate")
    if not isinstance(rate, (int, float)) or isinstance(rate, bool) or not 0 < rate < 1:
        missing.append("an approved discount rate")
    if service_assumptions.get("usage_forecast_confirmed") is not True:
        missing.append("a usage forecast confirmed by the workload owner")
    return missing


def commitment_coverage(telemetry: dict[str, Any], thresholds: dict[str, float], assumptions: dict[str, Any]) -> list[Finding]:
    """CMT-001: steady on-demand spend with low commitment coverage."""
    findings = []
    approved = assumptions.get("commitments", {})
    for row in telemetry["aws"].get("commitments", []):
        history = row["monthly_on_demand_usd"]
        if len(history) < thresholds["min_months"] or row["coverage_ratio"] > thresholds["max_coverage_ratio"]:
            continue
        average = mean(history)
        if average == 0:
            continue
        variation = round(pstdev(history) / average, 4)
        if variation > thresholds["max_coefficient_of_variation"]:
            continue
        service_assumptions = approved.get(row["service"], {})
        missing = missing_commitment_evidence(len(history), service_assumptions, thresholds["complete_evidence_months"])
        floor = min(history)
        if missing:
            recommendation = "No purchase recommendation: evidence is incomplete (missing " + ", ".join(missing) + ")."
            impact = EstimatedImpact.not_estimated("Not estimated: " + ", ".join(missing) + " not supplied.")
            action = "Collect missing evidence before any commitment"
        else:
            rate = service_assumptions["discount_rate"]
            recommendation = (
                "Evidence is complete: evaluate a commitment sized at or below the lowest observed month, after the owner confirms the forecast period."
            )
            impact = EstimatedImpact(
                value=round(floor * rate, 2),
                unit="USD per month",
                basis="lowest observed monthly on-demand cost multiplied by the approved discount rate",
            )
            action = "Evaluate a commitment sized to the lowest month"
        findings.append(
            Finding(
                rule_id="CMT-001",
                provider="aws",
                title="Steady on-demand usage with low commitment coverage",
                subject=row["service"],
                priority="low",
                evidence_source="aws.commitments",
                observed_evidence={
                    "service": row["service"],
                    "monthly_on_demand_usd": list(history),
                    "coverage_ratio": row["coverage_ratio"],
                },
                calculation=Calculation(
                    inputs={
                        "months": len(history),
                        "coverage_ratio": row["coverage_ratio"],
                        "max_coverage_ratio": thresholds["max_coverage_ratio"],
                        "max_coefficient_of_variation": thresholds["max_coefficient_of_variation"],
                    },
                    formula="coefficient_of_variation = population_stdev(monthly_on_demand_usd) / mean(monthly_on_demand_usd)",
                    result={
                        "coefficient_of_variation": variation,
                        "mean_monthly_usd": round(average, 2),
                        "lowest_monthly_usd": round(floor, 2),
                        "missing_evidence": missing,
                    },
                    units={"monthly_on_demand_usd": "USD per month", "coverage_ratio": "ratio", "coefficient_of_variation": "ratio"},
                    assumptions=(
                        "Past monthly usage does not guarantee future usage.",
                        "A purchase is only considered when history, discount rate, and forecast confirmation are all supplied.",
                    ),
                ),
                recommendation=recommendation,
                action=action,
                estimated_impact=impact,
                weight=average,
                confidence="medium",
            )
        )
    return findings

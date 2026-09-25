"""AWS rules. Inputs come from Cost Explorer groupings and, when approved, utilization metrics."""

from __future__ import annotations

from typing import Any

from .model import Calculation, EstimatedImpact, Finding, ratio

UNTAGGED = "(untagged)"
OBSERVED_INCREASE = "Not estimated: the increase is observed evidence; the avoidable share is unknown until the workload is reviewed."


def _baseline_anomaly(cost: float, baseline: float, thresholds: dict[str, float]) -> bool:
    """Shared anomaly test. A zero baseline is skipped because a ratio is undefined for new spend."""
    if baseline <= 0:
        return False
    return cost >= thresholds["min_ratio_to_baseline"] * baseline and cost - baseline >= thresholds["min_increase_usd"]


def _anomaly_calculation(cost: float, baseline: float, thresholds: dict[str, float], grouping: str) -> Calculation:
    return Calculation(
        inputs={
            "cost_usd": cost,
            "baseline_usd": baseline,
            "min_ratio_to_baseline": thresholds["min_ratio_to_baseline"],
            "min_increase_usd": thresholds["min_increase_usd"],
        },
        formula=(
            "increase_usd = cost_usd - baseline_usd; ratio = cost_usd / baseline_usd; "
            "fires when ratio >= min_ratio_to_baseline and increase_usd >= min_increase_usd"
        ),
        result={"increase_usd": round(cost - baseline, 2), "ratio_to_baseline": ratio(cost, baseline)},
        units={"cost_usd": "USD per assessment period", "baseline_usd": "USD per assessment period", "ratio_to_baseline": "ratio"},
        assumptions=(
            f"Cost is grouped by {grouping} for the assessment period.",
            "The baseline is the declared comparison period, not a forecast or a budget.",
        ),
    )


def service_region_cost_anomaly(telemetry: dict[str, Any], thresholds: dict[str, float], _: dict[str, Any]) -> list[Finding]:
    """AWS-001: service cost in a region rose above its baseline."""
    findings = []
    for row in telemetry["aws"].get("costs", []):
        if not _baseline_anomaly(row["cost_usd"], row["baseline_usd"], thresholds):
            continue
        findings.append(
            Finding(
                rule_id="AWS-001",
                provider="aws",
                title="Service cost in a region exceeds its baseline",
                subject=f"{row['service']} / {row['region']}",
                priority="high",
                evidence_source="aws.costs",
                observed_evidence={
                    "service": row["service"],
                    "region": row["region"],
                    "cost_usd": row["cost_usd"],
                    "baseline_usd": row["baseline_usd"],
                },
                calculation=_anomaly_calculation(row["cost_usd"], row["baseline_usd"], thresholds, "service and region"),
                recommendation="Inspect workload changes, tags, and query patterns for this service and region before changing reservations or commitments.",
                action="Explain the service and region cost increase",
                estimated_impact=EstimatedImpact.not_estimated(OBSERVED_INCREASE),
                weight=row["cost_usd"] - row["baseline_usd"],
                confidence="medium",
            )
        )
    return findings


def tag_cost_anomaly(telemetry: dict[str, Any], thresholds: dict[str, float], _: dict[str, Any]) -> list[Finding]:
    """AWS-002: cost allocated to a tag value (or to untagged spend) rose above its baseline."""
    findings = []
    for row in telemetry["aws"].get("tag_costs", []):
        if not _baseline_anomaly(row["cost_usd"], row["baseline_usd"], thresholds):
            continue
        value = row["tag_value"] if row["tag_value"] is not None else UNTAGGED
        findings.append(
            Finding(
                rule_id="AWS-002",
                provider="aws",
                title="Tagged cost allocation exceeds its baseline",
                subject=f"{row['tag_key']}={value}",
                priority="medium",
                evidence_source="aws.tag_costs",
                observed_evidence={
                    "tag_key": row["tag_key"],
                    "tag_value": value,
                    "cost_usd": row["cost_usd"],
                    "baseline_usd": row["baseline_usd"],
                },
                calculation=_anomaly_calculation(row["cost_usd"], row["baseline_usd"], thresholds, "cost-allocation tag value"),
                recommendation=(
                    "Assign an owner to untagged spend and enforce the tag before analysing the increase."
                    if value == UNTAGGED
                    else "Ask the owner of this tag value to explain the increase before changing resources."
                ),
                action="Attribute untagged spend to an owner" if value == UNTAGGED else "Ask the tag owner to explain the increase",
                estimated_impact=EstimatedImpact.not_estimated(OBSERVED_INCREASE),
                weight=row["cost_usd"] - row["baseline_usd"],
                confidence="medium",
            )
        )
    return findings


def idle_data_resources(telemetry: dict[str, Any], thresholds: dict[str, float], _: dict[str, Any]) -> list[Finding]:
    """AWS-003: a data-platform resource stayed underutilized for a long enough window."""
    findings = []
    for resource in telemetry["aws"].get("resources", []):
        if resource["observed_days"] < thresholds["min_observed_days"]:
            continue
        if resource["utilization"] > thresholds["max_utilization"]:
            continue
        idle_cost = round(resource["monthly_cost_usd"] * (1 - resource["utilization"]), 2)
        findings.append(
            Finding(
                rule_id="AWS-003",
                provider="aws",
                title="Data-platform resource is underutilized",
                subject=resource["resource_id"],
                priority="low",
                evidence_source="aws.resources",
                observed_evidence={
                    "resource_id": resource["resource_id"],
                    "type": resource["type"],
                    "utilization": resource["utilization"],
                    "observed_days": resource["observed_days"],
                    "monthly_cost_usd": resource["monthly_cost_usd"],
                },
                calculation=Calculation(
                    inputs={
                        "utilization": resource["utilization"],
                        "observed_days": resource["observed_days"],
                        "monthly_cost_usd": resource["monthly_cost_usd"],
                        "max_utilization": thresholds["max_utilization"],
                        "min_observed_days": thresholds["min_observed_days"],
                    },
                    formula="idle_cost_usd = monthly_cost_usd * (1 - utilization)",
                    result={"idle_cost_usd": idle_cost},
                    units={"utilization": "ratio", "monthly_cost_usd": "USD per month", "idle_cost_usd": "USD per month"},
                    assumptions=(
                        "Utilization comes from approved metric telemetry averaged over observed_days.",
                        "Cost is assumed to scale linearly with provisioned capacity; minimum sizes and dependencies can make the real reduction smaller.",
                    ),
                ),
                recommendation="Confirm dependencies and service-level requirements with the owner before resizing, pausing, or retiring the resource.",
                action="Confirm owner and dependencies before resizing",
                estimated_impact=EstimatedImpact(
                    value=idle_cost,
                    unit="USD per month (upper bound)",
                    basis="Cost share attributed to unused capacity under the linear-cost assumption; it is not a confirmed saving.",
                ),
                weight=idle_cost,
                confidence="low",
            )
        )
    return findings

"""Cloud Storage rules. Inputs come from Storage Insights inventory metadata only (object counts and sizes)."""

from __future__ import annotations

from typing import Any

from .model import Calculation, EstimatedImpact, Finding, ratio


def growth_without_expiry(telemetry: dict[str, Any], thresholds: dict[str, float], _: dict[str, Any]) -> list[Finding]:
    """GCS-001: a prefix gains objects every day, almost never deletes any, and its bucket has no lifecycle rule."""
    findings = []
    for prefix in telemetry["gcp"].get("storage_prefixes", []):
        added, deleted = prefix["objects_added_per_day"], prefix["objects_deleted_per_day"]
        if prefix["lifecycle_rule"] or added < thresholds["min_objects_added_per_day"]:
            continue
        deleted_ratio = ratio(deleted, added)
        if deleted_ratio > thresholds["max_deleted_to_added_ratio"]:
            continue
        avg_object_bytes = prefix["total_bytes"] / prefix["object_count"] if prefix["object_count"] else 0
        growth_gb_30d = round((added - deleted) * avg_object_bytes * 30 / 10**9, 1)
        subject = f"gs://{prefix['bucket']}/{prefix['prefix']}"
        findings.append(
            Finding(
                rule_id="GCS-001",
                provider="gcp",
                title="Objects accumulate with no expiry",
                subject=subject,
                priority="medium",
                evidence_source="gcp.gcs_prefixes",
                observed_evidence={
                    "object_count": prefix["object_count"],
                    "total_bytes": prefix["total_bytes"],
                    "added_per_day": added,
                    "deleted_per_day": deleted,
                },
                calculation=Calculation(
                    inputs={
                        "objects_added_per_day": added,
                        "objects_deleted_per_day": deleted,
                        "avg_object_bytes": round(avg_object_bytes),
                        "days": 30,
                    },
                    formula="growth_gb_30d = (objects_added_per_day - objects_deleted_per_day) * avg_object_bytes * 30 / 10^9",
                    result={"deleted_to_added_ratio": deleted_ratio, "growth_gb_30d": growth_gb_30d},
                    units={"total_bytes": "bytes", "growth_gb_30d": "GB (10^9 bytes)"},
                    assumptions=(
                        "Counts come from the Storage Insights inventory over the assessment window.",
                        "Storage is billed on average bytes held during the month, so a cleanup shows fully only in the next billing cycle.",
                    ),
                ),
                recommendation=(
                    "Confirm with the owner how many versions are needed, then add a lifecycle rule (age or number of newer "
                    "versions) and delete the backlog once."
                ),
                action="Add a lifecycle rule and clear the backlog",
                estimated_impact=EstimatedImpact(
                    value=growth_gb_30d,
                    unit="GB of new stored data per 30 days at the observed rate",
                    basis="Net growth of this prefix; no storage price is applied.",
                ),
                weight=growth_gb_30d,
                confidence="medium",
            )
        )
    return findings

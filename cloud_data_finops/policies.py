from __future__ import annotations

from typing import Any


BIGQUERY_BYTES_THRESHOLD = 1_000_000_000_000


def evaluate(specification: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for job in specification["gcp"].get("jobs", []):
        if job["bytes_billed"] > BIGQUERY_BYTES_THRESHOLD and not job["partition_pruned"]:
            findings.append({
                "id": "BQ-001",
                "provider": "gcp",
                "title": "High-volume BigQuery job without partition pruning",
                "evidence": {
                    "job_id": job["job_id"],
                    "bytes_billed": job["bytes_billed"],
                    "bytes_billed_gb": job["bytes_billed"] / 1_000_000_000,
                    "partition_pruned": False,
                },
                "assumption": "Bytes billed are used as a volume signal; pricing is not inferred from this fixture.",
                "recommendation": "Review partition filters and validate the query plan before changing the workload.",
                "confidence": "high",
            })

    for cost in specification["aws"].get("costs", []):
        if cost["baseline_usd"] > 0 and cost["cost_usd"] >= cost["baseline_usd"] * 1.5:
            findings.append({
                "id": "AWS-001",
                "provider": "aws",
                "title": "AWS service cost exceeds the declared baseline",
                "evidence": {
                    "service": cost["service"],
                    "region": cost["region"],
                    "cost_usd": cost["cost_usd"],
                    "baseline_usd": cost["baseline_usd"],
                    "increase_usd": cost["cost_usd"] - cost["baseline_usd"],
                },
                "assumption": "The fixture baseline is a comparison point, not a forecast or a savings commitment.",
                "recommendation": "Inspect workload, tags, and query patterns before changing reservations or commitments.",
                "confidence": "medium",
            })
    return findings


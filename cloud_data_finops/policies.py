from __future__ import annotations

from typing import Any
from collections import defaultdict


BIGQUERY_BYTES_THRESHOLD = 1_000_000_000_000


def evaluate(specification: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    jobs_by_fingerprint: dict[str, list[dict[str, Any]]] = defaultdict(list)
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
        fingerprint = job.get("fingerprint")
        if isinstance(fingerprint, str) and fingerprint:
            jobs_by_fingerprint[fingerprint].append(job)

    for fingerprint, matching_jobs in jobs_by_fingerprint.items():
        total_bytes = sum(item["bytes_billed"] for item in matching_jobs)
        if len(matching_jobs) >= 2 and total_bytes > BIGQUERY_BYTES_THRESHOLD:
            findings.append({
                "id": "BQ-002",
                "provider": "gcp",
                "title": "Repeated high-volume BigQuery query pattern",
                "evidence": {"fingerprint": fingerprint, "run_count": len(matching_jobs), "bytes_billed": total_bytes},
                "assumption": "The fingerprint is provided by the approved telemetry and does not expose query text.",
                "recommendation": "Review scheduling, materialization, and caching options before changing the workload.",
                "confidence": "medium",
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
    for resource in specification["aws"].get("resources", []):
        if resource.get("utilization", 1) < 0.1:
            findings.append({
                "id": "AWS-002",
                "provider": "aws",
                "title": "Underutilized AWS data resource",
                "evidence": {"resource_id": resource["resource_id"], "type": resource["type"], "utilization": resource["utilization"]},
                "assumption": "Utilization is a fixture signal and does not prove that the resource can be removed.",
                "recommendation": "Confirm workload dependencies and service-level requirements before resizing or retiring the resource.",
                "confidence": "low",
            })
    return findings

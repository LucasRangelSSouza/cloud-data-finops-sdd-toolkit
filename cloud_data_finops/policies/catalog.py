"""Rule catalog. docs/rule-catalog.md documents the same entries for readers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import aws, bigquery, commitments
from .model import Finding

RuleFunction = Callable[[dict[str, Any], dict[str, float], dict[str, Any]], list[Finding]]


@dataclass(frozen=True)
class Rule:
    rule_id: str
    provider: str
    name: str
    evidence_source: str
    thresholds: dict[str, float]
    evaluate: RuleFunction


RULES: dict[str, Rule] = {
    rule.rule_id: rule
    for rule in (
        Rule("BQ-001", "gcp", "Excessive bytes scanned", "gcp.jobs", {"bytes_billed": 1_000_000_000_000}, bigquery.excessive_bytes_scanned),
        Rule(
            "BQ-002",
            "gcp",
            "Repeated expensive queries",
            "gcp.jobs",
            {"min_runs": 3, "total_bytes_billed": 1_000_000_000_000},
            bigquery.repeated_expensive_queries,
        ),
        Rule("BQ-003", "gcp", "Missing partition pruning", "gcp.jobs", {"min_bytes_billed": 100_000_000_000}, bigquery.missing_partition_pruning),
        Rule(
            "BQ-004",
            "gcp",
            "Inefficient scheduling pattern",
            "gcp.schedules",
            {"min_run_to_update_ratio": 2.0, "min_excess_runs_per_day": 1.0},
            bigquery.inefficient_scheduling,
        ),
        Rule(
            "BQ-005",
            "gcp",
            "Reservation slot utilization observation",
            "gcp.reservations",
            {"max_avg_utilization": 0.30, "min_hours_observed": 168},
            bigquery.reservation_utilization,
        ),
        Rule(
            "AWS-001",
            "aws",
            "Service and region cost anomaly",
            "aws.costs",
            {"min_ratio_to_baseline": 1.5, "min_increase_usd": 100.0},
            aws.service_region_cost_anomaly,
        ),
        Rule(
            "AWS-002",
            "aws",
            "Tag cost anomaly",
            "aws.tag_costs",
            {"min_ratio_to_baseline": 1.5, "min_increase_usd": 100.0},
            aws.tag_cost_anomaly,
        ),
        Rule(
            "AWS-003",
            "aws",
            "Idle or underutilized data-platform resource",
            "aws.resources",
            {"max_utilization": 0.10, "min_observed_days": 14},
            aws.idle_data_resources,
        ),
        Rule(
            "CMT-001",
            "aws",
            "Commitment and discount coverage observation",
            "aws.commitments",
            {"min_months": 3, "max_coverage_ratio": 0.5, "max_coefficient_of_variation": 0.15, "complete_evidence_months": 12},
            commitments.commitment_coverage,
        ),
    )
}

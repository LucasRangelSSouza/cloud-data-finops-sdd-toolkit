"""Synthetic multi-cloud telemetry generator.

The output is a complete assessment specification with fixture telemetry. A
seeded random generator produces background records that stay below every rule
threshold; a fixed set of planted scenarios exercises each rule. The same seed
always yields byte-identical JSON, and tests/fixtures/assessment.json is the
output for DEFAULT_SEED.

All identifiers and amounts are invented. They describe no organization,
project, account, or bill.
"""

from __future__ import annotations

import json
import random
from copy import deepcopy
from typing import Any

DEFAULT_SEED = 20260901
GB = 10**9

PLANTED_JOBS = [
    # BQ-001 and BQ-003: one oversized scheduled job that reads a partitioned table without pruning.
    {
        "job_id": "job-expensive",
        "fingerprint": "fp-orders-full-scan",
        "bytes_billed": 3_000 * GB,
        "references_partitioned_table": True,
        "partition_pruned": False,
        "scheduled": True,
    },
    # BQ-003 only: below the BQ-001 volume threshold.
    {
        "job_id": "job-events-scan",
        "fingerprint": "fp-events-scan",
        "bytes_billed": 250 * GB,
        "references_partitioned_table": True,
        "partition_pruned": False,
        "scheduled": False,
    },
    # BQ-002: the same fingerprint runs three times with 1.2 TB in total.
    *[
        {
            "job_id": f"job-cohort-{index}",
            "fingerprint": "fp-adhoc-cohort",
            "bytes_billed": 400 * GB,
            "references_partitioned_table": True,
            "partition_pruned": True,
            "scheduled": False,
        }
        for index in (1, 2, 3)
    ],
]
PLANTED_SCHEDULES = [
    # BQ-004: six runs per day against a source that changes once per day.
    {"fingerprint": "fp-hourly-kpi-refresh", "runs_per_day": 6, "source_updates_per_day": 1, "avg_bytes_billed": 50 * GB},
    {"fingerprint": "fp-daily-snapshot", "runs_per_day": 1, "source_updates_per_day": 1, "avg_bytes_billed": 20 * GB},
    {"fingerprint": "fp-quarter-hour-feed", "runs_per_day": 4, "source_updates_per_day": 3, "avg_bytes_billed": 5 * GB},
]
PLANTED_RESERVATIONS = [
    # BQ-005: average use is 18% of the baseline over 720 observed hours.
    {"reservation_id": "res-batch-etl", "baseline_slots": 500, "avg_slots_used": 90.0, "peak_slots_used": 420.0, "hours_observed": 720},
    {"reservation_id": "res-interactive", "baseline_slots": 200, "avg_slots_used": 150.0, "peak_slots_used": 260.0, "hours_observed": 720},
]
PLANTED_COSTS = [
    # AWS-001: Athena doubles against its baseline; Glue rises by 60%.
    {"service": "Amazon Athena", "region": "us-east-1", "cost_usd": 1400.0, "baseline_usd": 700.0},
    {"service": "AWS Glue", "region": "us-east-1", "cost_usd": 480.0, "baseline_usd": 300.0},
    # Below the ratio threshold.
    {"service": "Amazon EMR", "region": "us-west-2", "cost_usd": 140.0, "baseline_usd": 100.0},
    {"service": "Amazon S3", "region": "us-east-1", "cost_usd": 120.0, "baseline_usd": 125.0},
]
PLANTED_TAG_COSTS = [
    # AWS-002: untagged spend more than doubles.
    {"tag_key": "team", "tag_value": None, "cost_usd": 650.0, "baseline_usd": 300.0},
    {"tag_key": "team", "tag_value": "analytics", "cost_usd": 900.0, "baseline_usd": 850.0},
    {"tag_key": "team", "tag_value": "ml-platform", "cost_usd": 300.0, "baseline_usd": 280.0},
]
PLANTED_RESOURCES = [
    # AWS-003: 4% average utilization over 30 days.
    {"resource_id": "redshift-reporting", "type": "redshift-cluster", "utilization": 0.04, "observed_days": 30, "monthly_cost_usd": 2200.0},
    # Too little telemetry to judge: 7 observed days.
    {"resource_id": "emr-sandbox", "type": "emr-cluster", "utilization": 0.08, "observed_days": 7, "monthly_cost_usd": 600.0},
    {"resource_id": "athena-wg-analytics", "type": "athena-workgroup", "utilization": 0.45, "observed_days": 30, "monthly_cost_usd": 0.0},
]
PLANTED_COMMITMENTS = [
    # CMT-001: steady Glue usage without coverage; six months is not enough for a purchase recommendation.
    {"service": "AWS Glue", "monthly_on_demand_usd": [410.0, 395.0, 420.0, 405.0, 415.0, 400.0], "coverage_ratio": 0.0},
    # Volatile usage: no observation.
    {"service": "Amazon Athena", "monthly_on_demand_usd": [300.0, 520.0, 700.0, 910.0, 1150.0, 1400.0], "coverage_ratio": 0.0},
]
BACKGROUND_SERVICES = [
    ("Amazon DynamoDB", "us-east-1"),
    ("Amazon Kinesis", "us-east-1"),
    ("Amazon Redshift", "us-east-1"),
    ("AWS Lambda", "us-west-2"),
    ("Amazon CloudWatch", "us-east-1"),
]


def _background_jobs(rng: random.Random, count: int) -> list[dict[str, Any]]:
    jobs = []
    for index in range(1, count + 1):
        partitioned = rng.random() < 0.6
        jobs.append(
            {
                "job_id": f"job-routine-{index:02d}",
                "fingerprint": f"fp-routine-{index:02d}",
                "bytes_billed": rng.randint(1, 90) * GB,
                "references_partitioned_table": partitioned,
                "partition_pruned": partitioned,
                "scheduled": rng.random() < 0.5,
            }
        )
    return jobs


def _background_costs(rng: random.Random) -> list[dict[str, Any]]:
    rows = []
    for service, region in BACKGROUND_SERVICES:
        baseline = float(rng.randint(40, 400))
        rows.append(
            {
                "service": service,
                "region": region,
                "cost_usd": round(baseline * rng.uniform(0.8, 1.3), 2),
                "baseline_usd": baseline,
            }
        )
    return rows


def generate_assessment(seed: int = DEFAULT_SEED) -> dict[str, Any]:
    rng = random.Random(seed)
    return deepcopy(
        {
            "schema_version": "1.1",
            "assessment_id": "demo-2026-09",
            "period": {"start": "2026-08-02", "end": "2026-08-31"},
            "scope": {
                "providers": ["gcp", "aws"],
                "retention_days": 30,
                "allow_live_collection": False,
                "data_origin": "synthetic",
                "generator": {"name": "cloud_data_finops.synthetic", "seed": seed},
            },
            "acceptance_criteria": [
                "Validation and preflight pass before any collector runs.",
                "Every enabled rule is evaluated against collected telemetry only.",
                "Every finding separates observed evidence, calculation, recommendation, estimated impact, and confidence.",
                "No finding states a monetary saving or a purchase recommendation without complete evidence.",
            ],
            "gcp": {
                "project_id": "demo-analytics",
                "location": "us",
                "roles": ["roles/bigquery.user", "roles/bigquery.resourceViewer"],
                "billing_export_dataset": None,
                "jobs": PLANTED_JOBS + _background_jobs(rng, 12),
                "schedules": PLANTED_SCHEDULES,
                "reservations": PLANTED_RESERVATIONS,
            },
            "aws": {
                "account_alias": "demo-data-account",
                "actions": [
                    "ce:GetCostAndUsage",
                    "ce:GetDimensionValues",
                    "ce:GetReservationCoverage",
                    "ce:GetSavingsPlansCoverage",
                    "cloudwatch:GetMetricData",
                ],
                "optional_telemetry": ["commitment_coverage", "resource_utilization"],
                "cost_allocation_tag": "team",
                "cur": {"enabled": False},
                "costs": PLANTED_COSTS + _background_costs(rng),
                "tag_costs": PLANTED_TAG_COSTS,
                "resources": PLANTED_RESOURCES,
                "commitments": PLANTED_COMMITMENTS,
            },
            "assumptions": {"commitments": {}},
        }
    )


def render_assessment(seed: int = DEFAULT_SEED) -> str:
    return json.dumps(generate_assessment(seed), indent=2) + "\n"

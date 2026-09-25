"""Fixture collection workflow: specification -> adapters -> validated telemetry."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .adapters import aws as aws_adapter
from .adapters import gcp as gcp_adapter

GCP_DATASETS = {"jobs": "jobs", "schedules": "schedules", "reservations": "reservations"}


class GcpFixtureClient:
    """Serves fixture rows as a single page per purpose. It never reads SQL results from a provider."""

    def __init__(self, gcp: dict[str, Any]) -> None:
        self._rows = {purpose: deepcopy(gcp.get(field, [])) for purpose, field in GCP_DATASETS.items()}
        self.queries: list[tuple[str, str]] = []

    def run_query(self, sql: str, *, purpose: str, page_token: str | None) -> dict[str, Any]:
        self.queries.append((purpose, sql))
        return {"rows": deepcopy(self._rows.get(purpose, [])), "next_page_token": None}


class AwsFixtureClient:
    """Serves fixture rows per read-only operation and grouping."""

    def __init__(self, aws: dict[str, Any]) -> None:
        self._aws = deepcopy(aws)
        self.operations: list[str] = []

    def call(self, operation: str, request: dict[str, Any], *, page_token: str | None) -> dict[str, Any]:
        self.operations.append(operation)
        if operation == "GetCostAndUsage":
            grouped_by_tag = request["GroupBy"][0]["Type"] == "TAG"
            rows = self._aws.get("tag_costs" if grouped_by_tag else "costs", [])
        elif operation == "GetMetricData":
            rows = self._aws.get("resources", [])
        elif operation == "GetSavingsPlansCoverage":
            rows = self._aws.get("commitments", [])
        else:
            rows = []
        return {"rows": deepcopy(rows), "next_page_token": None}


def collect_telemetry(specification: dict[str, Any], gcp_client: Any, aws_client: Any) -> dict[str, Any]:
    """Collect every approved dataset through the adapter seams and return a detached payload."""
    collected = deepcopy(specification)
    period = specification["period"]
    gcp_scope = collected["gcp"]
    aws_scope = collected["aws"]
    gcp_scope["jobs"] = gcp_adapter.collect_job_metadata(gcp_scope, period, gcp_client)
    gcp_scope["schedules"] = gcp_adapter.collect_schedule_metadata(gcp_scope, period, gcp_client)
    gcp_scope["reservations"] = gcp_adapter.collect_reservation_metadata(gcp_scope, period, gcp_client)
    aws_scope["costs"] = aws_adapter.collect_cost_metadata(aws_scope, period, aws_client)
    aws_scope["tag_costs"] = aws_adapter.collect_tag_costs(aws_scope, period, aws_client)
    aws_scope["resources"] = aws_adapter.collect_resource_utilization(aws_scope, period, aws_client)
    aws_scope["commitments"] = aws_adapter.collect_commitment_coverage(aws_scope, period, aws_client)
    return collected


def collect_fixture_telemetry(specification: dict[str, Any]) -> dict[str, Any]:
    return collect_telemetry(specification, GcpFixtureClient(specification["gcp"]), AwsFixtureClient(specification["aws"]))

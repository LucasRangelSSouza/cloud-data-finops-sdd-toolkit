from __future__ import annotations

from copy import deepcopy
from typing import Any

from .adapters.aws import collect_cost_metadata
from .adapters.gcp import collect_job_metadata


class GcpFixtureClient:
    def __init__(self, jobs: list[dict[str, Any]]) -> None:
        self._jobs = deepcopy(jobs)

    def list_jobs(self, project_id: str) -> list[dict[str, Any]]:
        return deepcopy(self._jobs)


class AwsFixtureClient:
    def __init__(self, costs: list[dict[str, Any]]) -> None:
        self._costs = deepcopy(costs)

    def get_cost_and_usage(self, account_alias: str) -> list[dict[str, Any]]:
        return deepcopy(self._costs)


def collect_fixture_telemetry(specification: dict[str, Any]) -> dict[str, Any]:
    """Run the provider adapter seams with fixture clients and return a detached payload."""
    collected = deepcopy(specification)
    collected["gcp"]["jobs"] = collect_job_metadata(
        collected["gcp"], GcpFixtureClient(specification["gcp"].get("jobs", []))
    )
    collected["aws"]["costs"] = collect_cost_metadata(
        collected["aws"], AwsFixtureClient(specification["aws"].get("costs", []))
    )
    return collected


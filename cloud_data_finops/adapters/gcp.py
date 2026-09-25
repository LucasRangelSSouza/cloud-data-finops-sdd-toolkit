"""GCP metadata adapter.

The query templates are reviewed blueprints: every template passes the safety
guard in tests, but no template has been executed against a live project in
this release. Clients are injected, so the fixture path never touches a network.
"""

from __future__ import annotations

from typing import Any, Protocol

from ..safety import GcpApprovedScope, guard_bigquery_query
from .common import collect_pages


class GcpMetadataClient(Protocol):
    def run_query(self, sql: str, *, purpose: str, page_token: str | None) -> dict[str, Any]:
        """Run a guarded read-only metadata query and return one page: {"rows": [...], "next_page_token": ...}."""


JOBS_QUERY = """
SELECT job_id, query_info.query_hashes.normalized_literals AS fingerprint,
       total_bytes_billed AS bytes_billed, referenced_tables, creation_time
FROM `{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
WHERE job_type = 'QUERY' AND creation_time >= TIMESTAMP('{start}') AND creation_time < TIMESTAMP_ADD(TIMESTAMP('{end}'), INTERVAL 1 DAY)
"""

SCHEDULES_QUERY = """
WITH runs AS (
  SELECT query_info.query_hashes.normalized_literals AS fingerprint, total_bytes_billed, creation_time
  FROM `{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
  WHERE job_type = 'QUERY' AND STARTS_WITH(job_id, 'scheduled_query')
    AND creation_time >= TIMESTAMP('{start}') AND creation_time < TIMESTAMP_ADD(TIMESTAMP('{end}'), INTERVAL 1 DAY)
)
SELECT fingerprint, COUNT(*) AS runs, AVG(total_bytes_billed) AS avg_bytes_billed FROM runs GROUP BY fingerprint
"""

RESERVATIONS_QUERY = """
SELECT reservation_id, slots_assigned AS baseline_slots, period_slot_ms, period_start
FROM `{region}.INFORMATION_SCHEMA.RESERVATIONS_TIMELINE`
WHERE period_start >= TIMESTAMP('{start}') AND period_start < TIMESTAMP_ADD(TIMESTAMP('{end}'), INTERVAL 1 DAY)
"""

BILLING_QUERY = """
SELECT service.description AS service, SUM(cost) AS cost, currency
FROM `{project}.{dataset}.gcp_billing_export_v1`
WHERE usage_start_time >= TIMESTAMP('{start}') GROUP BY service, currency
"""


def _approved_scope(scope: dict[str, Any]) -> GcpApprovedScope:
    project_id = scope.get("project_id")
    if not isinstance(project_id, str) or not project_id:
        raise ValueError("GCP project_id is required for metadata collection")
    return GcpApprovedScope(project_id=project_id, billing_export_dataset=scope.get("billing_export_dataset"))


def _run(client: GcpMetadataClient, sql: str, purpose: str, dataset: str, approved: GcpApprovedScope) -> list[dict[str, Any]]:
    guard_bigquery_query(sql, approved)
    return collect_pages(
        f"bigquery:{purpose}",
        dataset,
        lambda token: client.run_query(sql, purpose=purpose, page_token=token),
    )


def _template_values(scope: dict[str, Any], period: dict[str, str]) -> dict[str, str]:
    return {"region": f"region-{scope.get('location', 'us')}", "start": period["start"], "end": period["end"]}


def collect_job_metadata(scope: dict[str, Any], period: dict[str, str], client: GcpMetadataClient) -> list[dict[str, Any]]:
    approved = _approved_scope(scope)
    return _run(client, JOBS_QUERY.format(**_template_values(scope, period)), "jobs", "gcp.jobs", approved)


def collect_schedule_metadata(scope: dict[str, Any], period: dict[str, str], client: GcpMetadataClient) -> list[dict[str, Any]]:
    approved = _approved_scope(scope)
    return _run(client, SCHEDULES_QUERY.format(**_template_values(scope, period)), "schedules", "gcp.schedules", approved)


def collect_reservation_metadata(scope: dict[str, Any], period: dict[str, str], client: GcpMetadataClient) -> list[dict[str, Any]]:
    approved = _approved_scope(scope)
    return _run(client, RESERVATIONS_QUERY.format(**_template_values(scope, period)), "reservations", "gcp.reservations", approved)


def collect_billing_costs(scope: dict[str, Any], period: dict[str, str], client: GcpMetadataClient) -> list[dict[str, Any]]:
    """Read the billing export only when the specification approves one dataset for it."""
    approved = _approved_scope(scope)
    if approved.billing_export_dataset is None:
        raise ValueError("billing export collection requires an approved billing_export_dataset")
    sql = BILLING_QUERY.format(project=approved.project_id, dataset=approved.billing_export_dataset, start=period["start"])
    return _run(client, sql, "billing", "gcp.billing_costs", approved)

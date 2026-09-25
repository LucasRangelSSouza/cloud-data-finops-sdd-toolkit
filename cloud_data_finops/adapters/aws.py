"""AWS metadata adapter.

Cost Explorer and CloudWatch calls go through a read-only operation allowlist.
The optional CUR path runs one aggregate query against the approved CUR table,
in the approved Athena workgroup, with results written only to the approved
results prefix. Clients are injected; the fixture path never touches a network.
"""

from __future__ import annotations

from typing import Any, Protocol

from ..safety import AthenaApprovedScope, guard_athena_query, guard_aws_operation, guard_s3_uri
from .common import collect_pages


class AwsMetadataClient(Protocol):
    def call(self, operation: str, request: dict[str, Any], *, page_token: str | None) -> dict[str, Any]:
        """Call one read-only API operation and return one page: {"rows": [...], "next_page_token": ...}."""


class AthenaClient(Protocol):
    def run_query(self, sql: str, *, workgroup: str, output_location: str, page_token: str | None) -> dict[str, Any]:
        """Run one guarded Athena query and return one page of aggregated rows."""


CUR_QUERY = """
SELECT line_item_product_code AS product_code, SUM(line_item_unblended_cost) AS cost_usd
FROM {database}.{table}
WHERE line_item_usage_start_date >= DATE '{start}' AND line_item_usage_start_date <= DATE '{end}'
GROUP BY line_item_product_code
"""


def _account_alias(scope: dict[str, Any]) -> str:
    alias = scope.get("account_alias")
    if not isinstance(alias, str) or not alias:
        raise ValueError("AWS account_alias is required for metadata collection")
    return alias


def _call(client: AwsMetadataClient, operation: str, request: dict[str, Any], dataset: str) -> list[dict[str, Any]]:
    guard_aws_operation(operation)
    return collect_pages(f"aws:{operation}", dataset, lambda token: client.call(operation, request, page_token=token))


def _time_period(period: dict[str, str]) -> dict[str, str]:
    return {"Start": period["start"], "End": period["end"]}


def collect_cost_metadata(scope: dict[str, Any], period: dict[str, str], client: AwsMetadataClient) -> list[dict[str, Any]]:
    request = {
        "Account": _account_alias(scope),
        "TimePeriod": _time_period(period),
        "Granularity": "MONTHLY",
        "Metrics": ["UnblendedCost"],
        "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}, {"Type": "DIMENSION", "Key": "REGION"}],
    }
    return _call(client, "GetCostAndUsage", request, "aws.costs")


def collect_tag_costs(scope: dict[str, Any], period: dict[str, str], client: AwsMetadataClient) -> list[dict[str, Any]]:
    tag_key = scope.get("cost_allocation_tag")
    if not tag_key:
        return []
    request = {
        "Account": _account_alias(scope),
        "TimePeriod": _time_period(period),
        "Granularity": "MONTHLY",
        "Metrics": ["UnblendedCost"],
        "GroupBy": [{"Type": "TAG", "Key": tag_key}],
    }
    return _call(client, "GetCostAndUsage", request, "aws.tag_costs")


def collect_resource_utilization(scope: dict[str, Any], period: dict[str, str], client: AwsMetadataClient) -> list[dict[str, Any]]:
    if "resource_utilization" not in scope.get("optional_telemetry", []):
        return []
    request = {"Account": _account_alias(scope), "TimePeriod": _time_period(period), "Statistic": "Average"}
    return _call(client, "GetMetricData", request, "aws.resources")


def collect_commitment_coverage(scope: dict[str, Any], period: dict[str, str], client: AwsMetadataClient) -> list[dict[str, Any]]:
    if "commitment_coverage" not in scope.get("optional_telemetry", []):
        return []
    request = {"Account": _account_alias(scope), "TimePeriod": _time_period(period), "Granularity": "MONTHLY"}
    return _call(client, "GetSavingsPlansCoverage", request, "aws.commitments")


def approved_athena_scope(scope: dict[str, Any]) -> AthenaApprovedScope:
    cur = scope.get("cur", {})
    required = ("approved_s3_prefix", "athena_workgroup", "glue_database", "table", "query_results_prefix")
    missing = [key for key in required if not isinstance(cur.get(key), str) or not cur.get(key)]
    if missing:
        raise ValueError("AWS CUR collection requires: " + ", ".join(missing))
    guard_s3_uri(cur["approved_s3_prefix"], (cur["approved_s3_prefix"],))
    return AthenaApprovedScope(
        workgroup=cur["athena_workgroup"],
        glue_database=cur["glue_database"],
        cur_table=cur["table"],
        cur_prefix=cur["approved_s3_prefix"],
        query_results_prefix=cur["query_results_prefix"],
    )


def collect_cur_costs(scope: dict[str, Any], period: dict[str, str], client: AthenaClient) -> list[dict[str, Any]]:
    """Aggregate CUR cost by product code. Runs only when CUR is enabled and fully scoped."""
    if not scope.get("cur", {}).get("enabled"):
        return []
    approved = approved_athena_scope(scope)
    sql = CUR_QUERY.format(database=approved.glue_database, table=approved.cur_table, start=period["start"], end=period["end"])
    output_location = approved.query_results_prefix
    guard_aws_operation("StartQueryExecution")
    guard_athena_query(sql, approved.workgroup, output_location, approved)
    return collect_pages(
        "athena:StartQueryExecution",
        "aws.cur_costs",
        lambda token: client.run_query(sql, workgroup=approved.workgroup, output_location=output_location, page_token=token),
    )

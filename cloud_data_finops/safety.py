"""Request guards for provider adapters.

Every query or API call an adapter sends passes through one of these guards
first. They reject write operations, business-table reads, unapproved billing
datasets, S3 locations outside the approved prefixes, and Athena calls outside
the approved workgroup. Rejection messages never repeat the rejected request,
because a query or path can itself carry sensitive names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


class SafetyViolation(PermissionError):
    """Raised when a request would cross the approved read-only boundary."""


READ_ONLY_AWS_OPERATIONS = frozenset(
    {
        "GetCostAndUsage",
        "GetDimensionValues",
        "GetSavingsPlansCoverage",
        "GetReservationCoverage",
        "GetMetricData",
        "StartQueryExecution",
        "GetQueryExecution",
        "GetQueryResults",
    }
)
# StartQueryExecution is allowed only through guard_athena_query, which pins the
# workgroup, output location, and catalog database before a query can start.

WRITE_KEYWORDS = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "CREATE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "EXPORT",
    "CALL",
    "EXECUTE",
    "DECLARE",
    "SET",
    "UNLOAD",
    "MSCK",
    "REPLACE",
)
_WRITE_PATTERN = re.compile(r"\b(" + "|".join(WRITE_KEYWORDS) + r")\b", re.IGNORECASE)
_TABLE_REFERENCE = re.compile(r"\b(?:FROM|JOIN)\s+(`[^`]+`|\"[^\"]+\"|[A-Za-z0-9_.\-]+)", re.IGNORECASE)
_METADATA_VIEW = re.compile(
    r"^(?:[a-z][a-z0-9\-]*\.)?region-[a-z0-9\-]+\.INFORMATION_SCHEMA\.(JOBS|JOBS_BY_PROJECT|RESERVATIONS|RESERVATIONS_TIMELINE)$",
    re.IGNORECASE,
)
_S3_URI = re.compile(r"^s3://([a-z0-9][a-z0-9.\-]{1,61}[a-z0-9])/(.+)$")


@dataclass(frozen=True)
class GcpApprovedScope:
    project_id: str
    billing_export_dataset: str | None = None


@dataclass(frozen=True)
class AthenaApprovedScope:
    workgroup: str
    glue_database: str
    cur_table: str
    cur_prefix: str
    query_results_prefix: str


def _strip_sql_comments(sql: str) -> str:
    without_block = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", " ", without_block)


def _require_single_read_statement(sql: str) -> str:
    cleaned = _strip_sql_comments(sql).strip()
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()
    if ";" in cleaned:
        raise SafetyViolation("multi-statement queries are not allowed")
    if not re.match(r"^(SELECT|WITH)\b", cleaned, re.IGNORECASE):
        raise SafetyViolation("only read-only SELECT queries are allowed")
    if _WRITE_PATTERN.search(cleaned):
        raise SafetyViolation("write or administrative SQL keywords are not allowed")
    return cleaned


def _table_references(sql: str) -> list[str]:
    references = []
    for match in _TABLE_REFERENCE.finditer(sql):
        reference = match.group(1).strip('`"')
        if reference.startswith("("):
            continue
        references.append(reference)
    return references


def guard_bigquery_query(sql: str, scope: GcpApprovedScope) -> None:
    """Allow only reads of job/reservation metadata views and the approved billing export."""
    cleaned = _require_single_read_statement(sql)
    references = _table_references(cleaned)
    if not references:
        raise SafetyViolation("query must read an approved metadata view")
    cte_names = {name.upper() for name in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s+AS\s*\(", cleaned, re.IGNORECASE)}
    for reference in references:
        if reference.upper() in cte_names or _METADATA_VIEW.match(reference):
            continue
        parts = reference.split(".")
        if len(parts) == 3 and parts[0] == scope.project_id and parts[2].startswith("gcp_billing_export"):
            if scope.billing_export_dataset is None:
                raise SafetyViolation("billing export access is not approved for this assessment")
            if parts[1] != scope.billing_export_dataset:
                raise SafetyViolation("query references an unapproved billing export dataset")
            continue
        raise SafetyViolation("query references a table outside the approved metadata views; business-table extraction is not allowed")


def guard_s3_uri(uri: str, approved_prefixes: tuple[str, ...]) -> None:
    match = _S3_URI.match(uri)
    if not match or ".." in match.group(2).split("/"):
        raise SafetyViolation("S3 location must be an s3://bucket/prefix URI without relative segments")
    for prefix in approved_prefixes:
        normalized = prefix if prefix.endswith("/") else prefix + "/"
        if uri == prefix or uri.startswith(normalized):
            return
    raise SafetyViolation("S3 location is outside the approved prefixes")


def guard_athena_query(sql: str, workgroup: str, output_location: str, scope: AthenaApprovedScope) -> None:
    """Allow only a read of the approved CUR table in the approved workgroup and results prefix."""
    if not workgroup or workgroup != scope.workgroup:
        raise SafetyViolation("Athena queries must run in the approved workgroup; unrestricted Athena access is not allowed")
    guard_s3_uri(output_location, (scope.query_results_prefix,))
    cleaned = _require_single_read_statement(sql)
    references = _table_references(cleaned)
    if not references:
        raise SafetyViolation("query must read the approved CUR table")
    for reference in references:
        if reference != f"{scope.glue_database}.{scope.cur_table}":
            raise SafetyViolation("query references a table outside the approved CUR table; business-table extraction is not allowed")


def guard_aws_operation(operation: str) -> None:
    if operation not in READ_ONLY_AWS_OPERATIONS:
        raise SafetyViolation("AWS operation is not in the read-only allowlist")

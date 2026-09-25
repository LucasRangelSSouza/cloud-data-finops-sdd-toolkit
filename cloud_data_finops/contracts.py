"""Assessment specification and telemetry contracts.

Error messages name the offending field path and the expected shape. They never
include the received value, so a malformed payload cannot leak through logs,
exceptions, or CLI output.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any


class SpecificationError(ValueError):
    """Raised when an assessment specification cannot be evaluated safely."""


class TelemetryContractError(ValueError):
    """Raised when collected telemetry does not match the declared contract."""


REQUIRED_TOP_LEVEL_FIELDS = {
    "schema_version",
    "assessment_id",
    "period",
    "scope",
    "gcp",
    "aws",
    "acceptance_criteria",
}
SUPPORTED_SCHEMA_VERSIONS = {"1.1"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
AWS_OPTIONAL_TELEMETRY = {"resource_utilization", "commitment_coverage"}


def load_specification(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise SpecificationError(f"cannot read specification: {error.strerror}") from None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise SpecificationError(f"invalid JSON at line {error.lineno}: {error.msg}") from None
    validate_specification(payload)
    return payload


def validate_specification(payload: Any) -> None:
    """Reject a specification that is incomplete or leaves fixture mode."""
    if not isinstance(payload, dict):
        raise SpecificationError("specification root must be an object")

    missing = sorted(REQUIRED_TOP_LEVEL_FIELDS - payload.keys())
    if missing:
        raise SpecificationError(f"missing required fields: {', '.join(missing)}. Add them to the specification before running any command")
    if payload["schema_version"] not in SUPPORTED_SCHEMA_VERSIONS:
        raise SpecificationError(f"schema_version must be one of: {', '.join(sorted(SUPPORTED_SCHEMA_VERSIONS))}")
    _require(isinstance(payload["assessment_id"], str) and payload["assessment_id"], "assessment_id must be a non-empty string")

    period = payload["period"]
    _require(isinstance(period, dict), "period must be an object with start and end dates")
    for key in ("start", "end"):
        _require(isinstance(period.get(key), str) and ISO_DATE.match(period[key]), f"period.{key} must be an ISO date (YYYY-MM-DD)")
    _require(period["start"] <= period["end"], "period.start must not be after period.end")

    scope = payload["scope"]
    _require(isinstance(scope, dict), "scope must be an object")
    providers = scope.get("providers")
    _require(isinstance(providers, list) and set(providers) == {"gcp", "aws"}, "scope.providers must contain exactly gcp and aws")
    _require(scope.get("allow_live_collection") is False, "fixture mode requires scope.allow_live_collection to be false")
    _require(scope.get("data_origin") == "synthetic", 'fixture mode requires scope.data_origin to be "synthetic"')
    retention = scope.get("retention_days")
    _require(
        isinstance(retention, int) and not isinstance(retention, bool) and 1 <= retention <= 400, "scope.retention_days must be an integer between 1 and 400"
    )

    criteria = payload["acceptance_criteria"]
    _require(
        isinstance(criteria, list) and criteria and all(isinstance(item, str) and item.strip() for item in criteria),
        "acceptance_criteria must be a non-empty list of statements that define a successful assessment",
    )

    gcp = payload["gcp"]
    _require(isinstance(gcp, dict), "gcp must be an object")
    _require(isinstance(gcp.get("project_id"), str) and gcp["project_id"], "gcp.project_id must be a non-empty string")
    _require(_is_string_list(gcp.get("roles")), "gcp.roles must be a list of role names")
    dataset = gcp.get("billing_export_dataset")
    _require(dataset is None or (isinstance(dataset, str) and dataset), "gcp.billing_export_dataset must be null or an approved dataset name")

    aws = payload["aws"]
    _require(isinstance(aws, dict), "aws must be an object")
    _require(isinstance(aws.get("account_alias"), str) and aws["account_alias"], "aws.account_alias must be a non-empty string")
    _require(_is_string_list(aws.get("actions")), "aws.actions must be a list of IAM action names")
    optional = aws.get("optional_telemetry", [])
    _require(_is_string_list(optional), "aws.optional_telemetry must be a list")
    unknown = sorted(set(optional) - AWS_OPTIONAL_TELEMETRY)
    _require(not unknown, f"aws.optional_telemetry contains unsupported entries: {', '.join(unknown)}")
    for dataset_name, telemetry_name in (("resources", "resource_utilization"), ("commitments", "commitment_coverage")):
        _require(
            not aws.get(dataset_name) or telemetry_name in optional,
            f'aws.{dataset_name} telemetry requires "{telemetry_name}" in aws.optional_telemetry',
        )
    _require(not aws.get("tag_costs") or aws.get("cost_allocation_tag"), "aws.tag_costs telemetry requires aws.cost_allocation_tag")
    cur = aws.get("cur", {"enabled": False})
    _require(isinstance(cur, dict) and isinstance(cur.get("enabled", False), bool), "aws.cur must be an object with a boolean enabled flag")

    rules = payload.get("rules")
    if rules is not None:
        _validate_rule_selection(rules)


def _validate_rule_selection(rules: Any) -> None:
    from .policies.catalog import RULES

    _require(isinstance(rules, dict), "rules must be an object")
    enabled = rules.get("enabled")
    if enabled is not None:
        _require(_is_string_list(enabled), "rules.enabled must be a list of rule identifiers")
        unknown = sorted(set(enabled) - RULES.keys())
        _require(not unknown, f"rules.enabled contains unknown rule identifiers: {', '.join(unknown)}")
    thresholds = rules.get("thresholds", {})
    _require(isinstance(thresholds, dict), "rules.thresholds must be an object keyed by rule identifier")
    for rule_id, overrides in thresholds.items():
        _require(rule_id in RULES, f"rules.thresholds contains an unknown rule identifier: {rule_id}")
        _require(isinstance(overrides, dict), f"rules.thresholds.{rule_id} must be an object")
        allowed = RULES[rule_id].thresholds
        for key, value in overrides.items():
            _require(key in allowed, f"rules.thresholds.{rule_id}.{key} is not a supported threshold")
            _require(_is_number(value) and value >= 0, f"rules.thresholds.{rule_id}.{key} must be a non-negative number")


# Telemetry schemas: field name -> (type check, expectation shown in errors).
def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _non_negative_number(value: Any) -> bool:
    return _is_number(value) and value >= 0


def _ratio(value: Any) -> bool:
    return _is_number(value) and 0 <= value <= 1


def _boolean(value: Any) -> bool:
    return isinstance(value, bool)


def _number_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_non_negative_number(item) for item in value)


def _optional_string(value: Any) -> bool:
    return value is None or _non_empty_string(value)


FieldSpec = tuple[Any, str]
TELEMETRY_SCHEMAS: dict[str, dict[str, FieldSpec]] = {
    "gcp.jobs": {
        "job_id": (_non_empty_string, "non-empty string"),
        "fingerprint": (_non_empty_string, "non-empty string"),
        "bytes_billed": (_non_negative_int, "non-negative integer"),
        "references_partitioned_table": (_boolean, "boolean"),
        "partition_pruned": (_boolean, "boolean"),
        "scheduled": (_boolean, "boolean"),
    },
    "gcp.schedules": {
        "fingerprint": (_non_empty_string, "non-empty string"),
        "runs_per_day": (_non_negative_number, "non-negative number"),
        "source_updates_per_day": (_non_negative_number, "non-negative number"),
        "avg_bytes_billed": (_non_negative_int, "non-negative integer"),
    },
    "gcp.reservations": {
        "reservation_id": (_non_empty_string, "non-empty string"),
        "baseline_slots": (_non_negative_int, "non-negative integer"),
        "avg_slots_used": (_non_negative_number, "non-negative number"),
        "peak_slots_used": (_non_negative_number, "non-negative number"),
        "hours_observed": (_non_negative_int, "non-negative integer"),
    },
    "gcp.billing_costs": {
        "service": (_non_empty_string, "non-empty string"),
        "cost": (_non_negative_number, "non-negative number"),
        "currency": (_non_empty_string, "non-empty string"),
    },
    "aws.cur_costs": {
        "product_code": (_non_empty_string, "non-empty string"),
        "cost_usd": (_non_negative_number, "non-negative number"),
    },
    "aws.costs": {
        "service": (_non_empty_string, "non-empty string"),
        "region": (_non_empty_string, "non-empty string"),
        "cost_usd": (_non_negative_number, "non-negative number"),
        "baseline_usd": (_non_negative_number, "non-negative number"),
    },
    "aws.tag_costs": {
        "tag_key": (_non_empty_string, "non-empty string"),
        "tag_value": (_optional_string, "null or non-empty string"),
        "cost_usd": (_non_negative_number, "non-negative number"),
        "baseline_usd": (_non_negative_number, "non-negative number"),
    },
    "aws.resources": {
        "resource_id": (_non_empty_string, "non-empty string"),
        "type": (_non_empty_string, "non-empty string"),
        "utilization": (_ratio, "number between 0 and 1"),
        "observed_days": (_non_negative_int, "non-negative integer"),
        "monthly_cost_usd": (_non_negative_number, "non-negative number"),
    },
    "aws.commitments": {
        "service": (_non_empty_string, "non-empty string"),
        "monthly_on_demand_usd": (_number_list, "non-empty list of non-negative numbers"),
        "coverage_ratio": (_ratio, "number between 0 and 1"),
    },
}


def validate_telemetry_rows(dataset: str, rows: Any) -> list[dict[str, Any]]:
    """Validate a list of telemetry rows and return detached copies of the declared fields."""
    schema = TELEMETRY_SCHEMAS[dataset]
    if not isinstance(rows, list):
        raise TelemetryContractError(f"{dataset}: expected a list of records")
    validated: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        location = f"{dataset}[{index}]"
        if not isinstance(row, dict):
            raise TelemetryContractError(f"{location}: expected an object")
        missing = sorted(schema.keys() - row.keys())
        if missing:
            raise TelemetryContractError(f"{location}: missing fields: {', '.join(missing)}")
        for field, (check, expectation) in schema.items():
            if not check(row[field]):
                raise TelemetryContractError(f"{location}.{field}: expected {expectation}")
        record = {field: row[field] for field in schema}
        if dataset == "gcp.reservations" and record["peak_slots_used"] < record["avg_slots_used"]:
            raise TelemetryContractError(f"{location}.peak_slots_used: must not be lower than avg_slots_used")
        if dataset == "gcp.jobs" and record["partition_pruned"] and not record["references_partitioned_table"]:
            raise TelemetryContractError(f"{location}.partition_pruned: requires references_partitioned_table")
        validated.append(record)
    return validated


def _require(condition: Any, message: str) -> None:
    if not condition:
        raise SpecificationError(message)


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

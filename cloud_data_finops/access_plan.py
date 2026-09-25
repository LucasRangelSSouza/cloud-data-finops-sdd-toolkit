from __future__ import annotations

from typing import Any

from .preflight import BILLING_DATASET_ROLE, FORBIDDEN_AWS_ACTIONS, FORBIDDEN_GCP_ROLES, approved_aws_actions


def build_access_plan(specification: dict[str, Any]) -> dict[str, Any]:
    """Build a reviewable request from already validated and preflighted scope."""
    gcp = specification["gcp"]
    aws = specification["aws"]
    cur = aws.get("cur", {})
    dataset = gcp.get("billing_export_dataset")
    cur_enabled = bool(cur.get("enabled", False))
    return {
        "assessment_id": specification["assessment_id"],
        "mode": "read-only",
        "period": dict(specification["period"]),
        "retention_days": specification["scope"]["retention_days"],
        "gcp": {
            "project_id": gcp["project_id"],
            "project_roles": sorted(gcp["roles"]),
            "dataset_roles": [{"dataset": dataset, "role": BILLING_DATASET_ROLE}] if dataset else [],
            "billing_export_dataset": dataset,
            "business_table_content_access": False,
            "prohibited_roles": sorted(FORBIDDEN_GCP_ROLES),
        },
        "aws": {
            "account_alias": aws["account_alias"],
            "actions": sorted(approved_aws_actions(specification)),
            "optional_telemetry": sorted(aws.get("optional_telemetry", [])),
            "cur": {
                "enabled": cur_enabled,
                "approved_s3_prefix": cur.get("approved_s3_prefix") if cur_enabled else None,
                "athena_workgroup": cur.get("athena_workgroup") if cur_enabled else None,
                "glue_database": cur.get("glue_database") if cur_enabled else None,
                "query_results_prefix": cur.get("query_results_prefix") if cur_enabled else None,
            },
            "business_data_write_access": False,
            "prohibited_actions": sorted(FORBIDDEN_AWS_ACTIONS),
        },
    }

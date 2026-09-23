from __future__ import annotations

from typing import Any


def build_access_plan(specification: dict[str, Any]) -> dict[str, Any]:
    """Build a reviewable request from already validated assessment scope."""
    gcp = specification["gcp"]
    aws = specification["aws"]
    cur = aws.get("cur", {})
    return {
        "assessment_id": specification["assessment_id"],
        "mode": "read-only",
        "gcp": {
            "project_id": gcp["project_id"],
            "roles": sorted(gcp["roles"]),
            "billing_export_dataset": gcp.get("billing_export_dataset"),
            "business_table_content_access": False,
        },
        "aws": {
            "account_alias": aws["account_alias"],
            "actions": sorted(aws["actions"]),
            "cur": {
                "enabled": bool(cur.get("enabled", False)),
                "approved_s3_prefix": cur.get("approved_s3_prefix"),
            },
            "business_data_write_access": False,
        },
    }


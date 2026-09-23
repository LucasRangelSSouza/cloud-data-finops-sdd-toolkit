from __future__ import annotations

from typing import Any


FORBIDDEN_GCP_ROLES = {"roles/owner", "roles/editor"}
FORBIDDEN_AWS_ACTIONS = {"AdministratorAccess", "*", "s3:*", "athena:*"}
REQUIRED_GCP_ROLES = {"roles/bigquery.user", "roles/bigquery.resourceViewer"}
REQUIRED_AWS_ACTIONS = {"ce:GetCostAndUsage", "ce:GetDimensionValues"}


def find_access_violations(specification: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    gcp_roles = set(specification["gcp"].get("roles", []))
    aws_actions = set(specification["aws"].get("actions", []))

    for role in sorted(gcp_roles & FORBIDDEN_GCP_ROLES):
        violations.append(f"GCP role is prohibited: {role}")
    for role in sorted(REQUIRED_GCP_ROLES - gcp_roles):
        violations.append(f"GCP role is required for job metadata: {role}")
    for action in sorted(aws_actions & FORBIDDEN_AWS_ACTIONS):
        violations.append(f"AWS permission is prohibited: {action}")
    for action in sorted(REQUIRED_AWS_ACTIONS - aws_actions):
        violations.append(f"AWS Cost Explorer action is required: {action}")

    billing_dataset = specification["gcp"].get("billing_export_dataset")
    if billing_dataset is not None and not isinstance(billing_dataset, str):
        violations.append("GCP billing_export_dataset must be null or an explicitly approved dataset name")

    cur = specification["aws"].get("cur", {})
    if cur.get("enabled") and not cur.get("approved_s3_prefix"):
        violations.append("AWS CUR requires an approved_s3_prefix")

    return violations


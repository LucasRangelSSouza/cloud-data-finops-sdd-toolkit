"""Least-privilege preflight.

`find_access_violations` checks the access an assessment requests.
`evaluate_grants` compares that request with the permissions a provider reports
as granted, so an over-broad grant blocks collection even when the request was
narrow.
"""

from __future__ import annotations

import re
from typing import Any

FORBIDDEN_GCP_ROLES = {"roles/owner", "roles/editor"}
REQUIRED_GCP_ROLES = {"roles/bigquery.user", "roles/bigquery.resourceViewer"}
BILLING_DATASET_ROLE = "roles/bigquery.dataViewer"
FORBIDDEN_AWS_ACTIONS = {"AdministratorAccess", "*", "s3:*", "athena:*", "glue:*", "ce:*"}
REQUIRED_AWS_ACTIONS = {"ce:GetCostAndUsage", "ce:GetDimensionValues"}
OPTIONAL_AWS_ACTIONS = {
    "resource_utilization": {"cloudwatch:GetMetricData"},
    "commitment_coverage": {"ce:GetSavingsPlansCoverage", "ce:GetReservationCoverage"},
}
CUR_AWS_ACTIONS = {
    "athena:StartQueryExecution",
    "athena:GetQueryExecution",
    "athena:GetQueryResults",
    "glue:GetDatabase",
    "glue:GetTable",
    "glue:GetPartitions",
    "s3:GetBucketLocation",
    "s3:GetObject",
    "s3:ListBucket",
    "s3:PutObject",
}
# Verbs that change state. s3:PutObject is the one exception: Athena must write
# query results, and evaluate_grants restricts it to the approved results prefix.
WRITE_VERB = re.compile(
    r"^[a-z0-9\-]+:(Put|Delete|Create|Update|Modify|Purchase|Attach|Detach|Tag|Untag|Accept|Terminate|Stop|Reboot|Restore|Set|Replace|Associate|Disassociate)"
)


def approved_aws_actions(specification: dict[str, Any]) -> set[str]:
    aws = specification["aws"]
    actions = set(REQUIRED_AWS_ACTIONS)
    for telemetry in aws.get("optional_telemetry", []):
        actions |= OPTIONAL_AWS_ACTIONS.get(telemetry, set())
    if aws.get("cur", {}).get("enabled"):
        actions |= CUR_AWS_ACTIONS
    return actions


def _is_prohibited_aws_action(action: str) -> bool:
    return action in FORBIDDEN_AWS_ACTIONS or "*" in action


def _cur_scope_violations(cur: dict[str, Any]) -> list[str]:
    if not cur.get("enabled"):
        return []
    violations = []
    prefix = cur.get("approved_s3_prefix")
    if not isinstance(prefix, str) or not re.match(r"^s3://[a-z0-9][a-z0-9.\-]+/.+", prefix):
        violations.append("AWS CUR requires an approved_s3_prefix of the form s3://bucket/prefix/ (a bucket root is not a prefix)")
    for key, label in (
        ("athena_workgroup", "a named Athena workgroup"),
        ("glue_database", "a named Glue database"),
        ("table", "the CUR table name"),
        ("query_results_prefix", "an approved Athena query_results_prefix"),
    ):
        if not isinstance(cur.get(key), str) or not cur.get(key):
            violations.append(f"AWS CUR requires {label} ({key})")
    results = cur.get("query_results_prefix")
    if isinstance(prefix, str) and isinstance(results, str) and results.startswith(prefix):
        violations.append("AWS CUR query_results_prefix must be outside the CUR report prefix")
    return violations


def find_access_violations(specification: dict[str, Any]) -> list[str]:
    """Check the requested access. Each message names the fix the reviewer should request."""
    violations: list[str] = []
    gcp = specification["gcp"]
    aws = specification["aws"]
    gcp_roles = set(gcp.get("roles", []))
    aws_actions = set(aws.get("actions", []))

    for role in sorted(gcp_roles & FORBIDDEN_GCP_ROLES):
        violations.append(f"GCP role is prohibited: {role}")
    if BILLING_DATASET_ROLE in gcp_roles:
        violations.append(f"GCP role {BILLING_DATASET_ROLE} must not be granted at project level; request it only on the approved billing export dataset")
    for role in sorted(gcp_roles - REQUIRED_GCP_ROLES - FORBIDDEN_GCP_ROLES - {BILLING_DATASET_ROLE}):
        violations.append(f"GCP role is broader than the approved scope: {role}")
    for role in sorted(REQUIRED_GCP_ROLES - gcp_roles):
        violations.append(f"GCP role is required for job metadata: {role}. Remediation: request {role} on project {gcp['project_id']}")

    approved = approved_aws_actions(specification)
    for action in sorted(aws_actions):
        if _is_prohibited_aws_action(action):
            violations.append(f"AWS permission is prohibited: {action}")
        elif WRITE_VERB.match(action) and action != "s3:PutObject":
            violations.append(f"AWS write permission is prohibited: {action}")
        elif action not in approved:
            violations.append(f"AWS permission is broader than the approved scope: {action}")
    for action in sorted(approved - aws_actions):
        violations.append(f"AWS action is required by the approved scope: {action}. Remediation: add {action} to the assessment policy")

    violations.extend(_cur_scope_violations(aws.get("cur", {})))
    return violations


def _s3_resource_prefix(resource: str) -> str | None:
    match = re.match(r"^arn:aws:s3:::(.+)$", resource)
    if not match:
        return None
    return "s3://" + match.group(1).rstrip("*")


def _within(location: str, prefix: str) -> bool:
    normalized = prefix if prefix.endswith("/") else prefix + "/"
    return location.startswith(normalized) or location + "/" == normalized


def _aws_statement_violations(statement: dict[str, Any], specification: dict[str, Any], approved: set[str]) -> list[str]:
    cur = specification["aws"].get("cur", {})
    violations = []
    actions = statement.get("actions", [])
    resources = statement.get("resources", [])
    for action in sorted(actions):
        if _is_prohibited_aws_action(action):
            violations.append(f"granted AWS permission is prohibited: {action}")
            continue
        if WRITE_VERB.match(action) and action != "s3:PutObject":
            violations.append(f"granted AWS write permission is prohibited: {action}")
            continue
        if action not in approved:
            violations.append(f"granted AWS permission is broader than the approved scope: {action}")
            continue
        service = action.split(":", 1)[0]
        if service == "athena":
            workgroup = cur.get("athena_workgroup")
            if any(resource == "*" or not resource.endswith(f":workgroup/{workgroup}") for resource in resources):
                violations.append(f"granted {action} is not limited to the approved Athena workgroup (unrestricted Athena access)")
        elif service == "glue":
            database = cur.get("glue_database")
            allowed = (":catalog", f":database/{database}", f":table/{database}/")
            if any(resource == "*" or not any(marker in resource for marker in allowed) for resource in resources):
                violations.append(f"granted {action} is not limited to the approved Glue database")
        elif service == "s3":
            prefixes = [cur.get("query_results_prefix")] if action == "s3:PutObject" else [cur.get("approved_s3_prefix"), cur.get("query_results_prefix")]
            prefixes = [prefix for prefix in prefixes if isinstance(prefix, str)]
            buckets = {prefix.split("/")[2] for prefix in prefixes}
            for resource in resources:
                location = _s3_resource_prefix(resource)
                if location is None:
                    violations.append(f"granted {action} uses a non-S3 or wildcard resource")
                    continue
                is_bucket = "/" not in location[len("s3://") :]
                if is_bucket and action in {"s3:ListBucket", "s3:GetBucketLocation"} and location[len("s3://") :] in buckets:
                    continue
                if not any(_within(location, prefix) for prefix in prefixes):
                    target = "results prefix" if action == "s3:PutObject" else "CUR or results prefix"
                    violations.append(f"granted {action} reaches an S3 location outside the approved {target}")
                    break
    return violations


def evaluate_grants(specification: dict[str, Any], grants: dict[str, Any]) -> dict[str, list[str]]:
    """Compare provider-reported grants with the approved request.

    Returns `violations` (grants broader than approved; collection must stop) and
    `missing` (approved access not yet granted, each with a remediation request).
    """
    violations: list[str] = []
    missing: list[str] = []
    gcp = specification["gcp"]
    gcp_grants = grants.get("gcp", {})
    project_roles = set(gcp_grants.get("project_roles", []))
    for role in sorted(project_roles & FORBIDDEN_GCP_ROLES):
        violations.append(f"granted GCP role is prohibited: {role}")
    for role in sorted(project_roles - REQUIRED_GCP_ROLES - FORBIDDEN_GCP_ROLES):
        violations.append(f"granted GCP project role is broader than the approved scope: {role}")
    for role in sorted(REQUIRED_GCP_ROLES - project_roles):
        missing.append(f"GCP role {role} is missing. Remediation: grant {role} on project {gcp['project_id']}")

    approved_dataset = gcp.get("billing_export_dataset")
    dataset_grants = gcp_grants.get("dataset_roles", [])
    for grant in dataset_grants:
        if grant.get("dataset") != approved_dataset:
            violations.append("granted GCP dataset access covers an unapproved dataset")
        elif grant.get("role") != BILLING_DATASET_ROLE:
            violations.append(f"granted GCP dataset role on the billing export must be {BILLING_DATASET_ROLE}")
    if approved_dataset and not any(grant.get("dataset") == approved_dataset for grant in dataset_grants):
        missing.append(
            f"GCP {BILLING_DATASET_ROLE} on the approved billing export dataset is missing. Remediation: grant it on dataset {approved_dataset} only"
        )

    aws_grants = grants.get("aws", {})
    for policy in sorted(aws_grants.get("managed_policies", [])):
        if policy == "AdministratorAccess":
            violations.append("granted AWS managed policy is prohibited: AdministratorAccess")
        else:
            violations.append(f"granted AWS managed policy is broader than the approved actions: {policy}")
    approved = approved_aws_actions(specification)
    granted_actions: set[str] = set()
    for statement in aws_grants.get("statements", []):
        if statement.get("effect", "Allow") != "Allow":
            continue
        granted_actions |= set(statement.get("actions", []))
        violations.extend(_aws_statement_violations(statement, specification, approved))
    for action in sorted(approved - granted_actions):
        missing.append(f"AWS action {action} is missing. Remediation: add {action} to the assessment policy")
    return {"violations": violations, "missing": missing}

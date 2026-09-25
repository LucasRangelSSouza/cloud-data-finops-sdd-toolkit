"""Access tests: least-privilege requests, remediation messages, scope boundaries, and broad-grant rejection."""

import json
import unittest
from copy import deepcopy

from cloud_data_finops.access_plan import build_access_plan
from cloud_data_finops.preflight import CUR_AWS_ACTIONS, evaluate_grants, find_access_violations
from tests.helpers import ROOT, load_fixture

GRANTS = ROOT / "tests" / "fixtures" / "grants"


def grants(name: str) -> dict:
    return json.loads((GRANTS / f"{name}.json").read_text(encoding="utf-8"))


def cur_specification() -> dict:
    specification = load_fixture()
    specification["gcp"]["billing_export_dataset"] = "billing_export"
    specification["aws"]["optional_telemetry"] = []
    specification["aws"]["resources"] = []
    specification["aws"]["commitments"] = []
    specification["aws"]["actions"] = sorted({"ce:GetCostAndUsage", "ce:GetDimensionValues"} | CUR_AWS_ACTIONS)
    specification["aws"]["cur"] = {
        "enabled": True,
        "approved_s3_prefix": "s3://demo-cost-reports/cur/daily/",
        "athena_workgroup": "finops-readonly",
        "glue_database": "cur_db",
        "table": "cur_daily",
        "query_results_prefix": "s3://demo-athena-results/finops/",
    }
    return specification


class RequestedAccessTests(unittest.TestCase):
    def test_fixture_request_is_least_privilege(self) -> None:
        self.assertEqual(find_access_violations(load_fixture()), [])

    def test_rejects_gcp_owner_and_editor(self) -> None:
        specification = load_fixture()
        specification["gcp"]["roles"] += ["roles/owner", "roles/editor"]
        violations = find_access_violations(specification)
        self.assertIn("GCP role is prohibited: roles/owner", violations)
        self.assertIn("GCP role is prohibited: roles/editor", violations)

    def test_rejects_project_level_data_viewer(self) -> None:
        specification = load_fixture()
        specification["gcp"]["roles"].append("roles/bigquery.dataViewer")
        self.assertTrue(any("must not be granted at project level" in item for item in find_access_violations(specification)))

    def test_rejects_administrator_access_wildcards_and_unrestricted_athena(self) -> None:
        specification = load_fixture()
        specification["aws"]["actions"] += ["AdministratorAccess", "*", "athena:*", "s3:*"]
        violations = find_access_violations(specification)
        for action in ("AdministratorAccess", "*", "athena:*", "s3:*"):
            self.assertIn(f"AWS permission is prohibited: {action}", violations)

    def test_rejects_write_actions_and_actions_outside_scope(self) -> None:
        specification = load_fixture()
        specification["aws"]["actions"] += ["s3:DeleteObject", "ce:CreateAnomalyMonitor", "athena:StartQueryExecution"]
        violations = find_access_violations(specification)
        self.assertIn("AWS write permission is prohibited: s3:DeleteObject", violations)
        self.assertIn("AWS write permission is prohibited: ce:CreateAnomalyMonitor", violations)
        self.assertIn("AWS permission is broader than the approved scope: athena:StartQueryExecution", violations)

    def test_missing_permissions_include_a_remediation_request(self) -> None:
        specification = load_fixture()
        specification["gcp"]["roles"] = ["roles/bigquery.user"]
        specification["aws"]["actions"].remove("cloudwatch:GetMetricData")
        violations = find_access_violations(specification)
        self.assertIn(
            "GCP role is required for job metadata: roles/bigquery.resourceViewer. "
            "Remediation: request roles/bigquery.resourceViewer on project demo-analytics",
            violations,
        )
        self.assertIn(
            "AWS action is required by the approved scope: cloudwatch:GetMetricData. Remediation: add cloudwatch:GetMetricData to the assessment policy",
            violations,
        )

    def test_cur_requires_a_complete_scoped_path(self) -> None:
        specification = cur_specification()
        self.assertEqual(find_access_violations(specification), [])
        for key in ("approved_s3_prefix", "athena_workgroup", "glue_database", "query_results_prefix"):
            broken = deepcopy(specification)
            del broken["aws"]["cur"][key]
            self.assertTrue(any(key in item for item in find_access_violations(broken)), key)

    def test_cur_rejects_a_bucket_root_and_results_inside_the_report_prefix(self) -> None:
        specification = cur_specification()
        specification["aws"]["cur"]["approved_s3_prefix"] = "s3://demo-cost-reports/"
        self.assertTrue(any("bucket root is not a prefix" in item for item in find_access_violations(specification)))
        specification = cur_specification()
        specification["aws"]["cur"]["query_results_prefix"] = "s3://demo-cost-reports/cur/daily/results/"
        self.assertIn("AWS CUR query_results_prefix must be outside the CUR report prefix", find_access_violations(specification))

    def test_access_plan_lists_dataset_scoped_billing_reader_and_cur_scope(self) -> None:
        plan = build_access_plan(cur_specification())
        self.assertEqual(plan["gcp"]["dataset_roles"], [{"dataset": "billing_export", "role": "roles/bigquery.dataViewer"}])
        self.assertNotIn("roles/bigquery.dataViewer", plan["gcp"]["project_roles"])
        self.assertEqual(plan["aws"]["cur"]["athena_workgroup"], "finops-readonly")
        self.assertFalse(plan["aws"]["business_data_write_access"])


class GrantedAccessTests(unittest.TestCase):
    def test_least_privilege_grants_pass(self) -> None:
        self.assertEqual(evaluate_grants(load_fixture(), grants("least-privilege")), {"violations": [], "missing": []})

    def test_cur_least_privilege_grants_pass(self) -> None:
        self.assertEqual(evaluate_grants(cur_specification(), grants("cur-least-privilege")), {"violations": [], "missing": []})

    def test_owner_and_administrator_access_grants_are_rejected(self) -> None:
        result = evaluate_grants(load_fixture(), grants("broad-owner-admin"))
        self.assertIn("granted GCP role is prohibited: roles/owner", result["violations"])
        self.assertIn("granted AWS managed policy is prohibited: AdministratorAccess", result["violations"])

    def test_editor_and_extra_project_roles_are_rejected(self) -> None:
        granted = grants("least-privilege")
        granted["gcp"]["project_roles"] += ["roles/editor", "roles/bigquery.dataOwner"]
        violations = evaluate_grants(load_fixture(), granted)["violations"]
        self.assertIn("granted GCP role is prohibited: roles/editor", violations)
        self.assertIn("granted GCP project role is broader than the approved scope: roles/bigquery.dataOwner", violations)

    def test_unapproved_dataset_is_rejected(self) -> None:
        granted = grants("cur-least-privilege")
        granted["gcp"]["dataset_roles"].append({"dataset": "sales_mart", "role": "roles/bigquery.dataViewer"})
        self.assertIn("granted GCP dataset access covers an unapproved dataset", evaluate_grants(cur_specification(), granted)["violations"])

    def test_write_role_on_the_billing_dataset_is_rejected(self) -> None:
        granted = grants("cur-least-privilege")
        granted["gcp"]["dataset_roles"] = [{"dataset": "billing_export", "role": "roles/bigquery.dataEditor"}]
        self.assertTrue(any("must be roles/bigquery.dataViewer" in item for item in evaluate_grants(cur_specification(), granted)["violations"]))

    def test_unapproved_s3_prefix_is_rejected(self) -> None:
        granted = grants("cur-least-privilege")
        granted["aws"]["statements"][4]["resources"].append("arn:aws:s3:::demo-cost-reports/finance/*")
        violations = evaluate_grants(cur_specification(), granted)["violations"]
        self.assertIn("granted s3:GetObject reaches an S3 location outside the approved CUR or results prefix", violations)

    def test_put_object_outside_the_results_prefix_is_rejected(self) -> None:
        granted = grants("cur-least-privilege")
        granted["aws"]["statements"][5]["resources"] = ["arn:aws:s3:::demo-cost-reports/cur/daily/*"]
        violations = evaluate_grants(cur_specification(), granted)["violations"]
        self.assertIn("granted s3:PutObject reaches an S3 location outside the approved results prefix", violations)

    def test_unrestricted_athena_is_rejected(self) -> None:
        granted = grants("cur-least-privilege")
        granted["aws"]["statements"][1]["resources"] = ["*"]
        violations = evaluate_grants(cur_specification(), granted)["violations"]
        self.assertTrue(any("unrestricted Athena access" in item for item in violations))
        granted["aws"]["statements"][1]["actions"] = ["athena:*"]
        self.assertIn("granted AWS permission is prohibited: athena:*", evaluate_grants(cur_specification(), granted)["violations"])

    def test_write_operations_are_rejected(self) -> None:
        granted = grants("least-privilege")
        granted["aws"]["statements"].append({"effect": "Allow", "actions": ["s3:DeleteObject", "ce:UpdateCostCategoryDefinition"], "resources": ["*"]})
        violations = evaluate_grants(load_fixture(), granted)["violations"]
        self.assertIn("granted AWS write permission is prohibited: s3:DeleteObject", violations)
        self.assertIn("granted AWS write permission is prohibited: ce:UpdateCostCategoryDefinition", violations)

    def test_missing_grants_produce_remediation_requests(self) -> None:
        granted = grants("least-privilege")
        granted["gcp"]["project_roles"] = ["roles/bigquery.user"]
        granted["aws"]["statements"][0]["actions"].remove("ce:GetDimensionValues")
        result = evaluate_grants(load_fixture(), granted)
        self.assertEqual(result["violations"], [])
        self.assertIn(
            "GCP role roles/bigquery.resourceViewer is missing. Remediation: grant roles/bigquery.resourceViewer on project demo-analytics",
            result["missing"],
        )
        self.assertIn("AWS action ce:GetDimensionValues is missing. Remediation: add ce:GetDimensionValues to the assessment policy", result["missing"])

    def test_missing_billing_dataset_grant_names_the_approved_dataset_only(self) -> None:
        granted = grants("cur-least-privilege")
        granted["gcp"]["dataset_roles"] = []
        missing = evaluate_grants(cur_specification(), granted)["missing"]
        self.assertTrue(any("grant it on dataset billing_export only" in item for item in missing))


if __name__ == "__main__":
    unittest.main()

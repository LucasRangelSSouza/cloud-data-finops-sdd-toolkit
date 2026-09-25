import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import FIXTURE, ROOT, load_fixture

GRANTS = ROOT / "tests" / "fixtures" / "grants"


class FinopsCliContractTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "cloud_data_finops.cli", *args],
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
        )

    def write_spec(self, directory: str, payload: dict) -> Path:
        path = Path(directory) / "spec.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_validate_accepts_the_declared_fixture_contract(self) -> None:
        completed = self.run_cli("validate", "--spec", str(FIXTURE))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("valid", completed.stdout)

    def test_validate_reports_an_actionable_message_for_missing_acceptance_criteria(self) -> None:
        payload = load_fixture()
        del payload["acceptance_criteria"]
        with tempfile.TemporaryDirectory() as directory:
            completed = self.run_cli("validate", "--spec", str(self.write_spec(directory, payload)))
        self.assertEqual(completed.returncode, 2)
        self.assertIn("missing required fields: acceptance_criteria", completed.stderr)

    def test_preflight_rejects_owner_and_administrator_access(self) -> None:
        payload = load_fixture()
        payload["gcp"]["roles"].append("roles/owner")
        payload["aws"]["actions"].append("AdministratorAccess")

        with tempfile.TemporaryDirectory() as directory:
            completed = self.run_cli("preflight", "--spec", str(self.write_spec(directory, payload)))

        self.assertEqual(completed.returncode, 2)
        self.assertIn("roles/owner", completed.stderr)
        self.assertIn("AdministratorAccess", completed.stderr)

    def test_preflight_rejects_a_cur_without_an_approved_prefix(self) -> None:
        payload = load_fixture()
        payload["aws"]["cur"] = {"enabled": True}

        with tempfile.TemporaryDirectory() as directory:
            completed = self.run_cli("preflight", "--spec", str(self.write_spec(directory, payload)))

        self.assertEqual(completed.returncode, 2)
        self.assertIn("approved_s3_prefix", completed.stderr)

    def test_preflight_compares_provider_grants(self) -> None:
        passed = self.run_cli("preflight", "--spec", str(FIXTURE), "--grants", str(GRANTS / "least-privilege.json"))
        rejected = self.run_cli("preflight", "--spec", str(FIXTURE), "--grants", str(GRANTS / "broad-owner-admin.json"))

        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("granted GCP role is prohibited: roles/owner", rejected.stderr)
        self.assertIn("AdministratorAccess", rejected.stderr)

    def test_report_writes_findings_markdown_chart_and_deck(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report"
            completed = self.run_cli("report", "--spec", str(FIXTURE), "--output", str(output))

            self.assertEqual(completed.returncode, 0, completed.stderr)
            findings = json.loads((output / "findings.json").read_text(encoding="utf-8"))
            report = (output / "report.md").read_text(encoding="utf-8")
            self.assertGreater((output / "cost-signals.png").stat().st_size, 1_000)
            self.assertTrue((output / "synthetic-finops-assessment.pptx").is_file())

        self.assertEqual(findings[0]["rule_id"], "AWS-001")
        self.assertIn("## Limitations", report)
        self.assertIn("Synthetic data", report)

    def test_deck_command_writes_only_the_deck(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            deck = Path(directory) / "deck.pptx"
            completed = self.run_cli("deck", "--spec", str(FIXTURE), "--output", str(deck))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(deck.is_file())

    def test_synth_reproduces_the_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "generated.json"
            completed = self.run_cli("synth", "--output", str(output))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(output.read_bytes(), FIXTURE.read_bytes())

    def test_access_plan_writes_provider_specific_read_only_requests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "access-plan.json"
            completed = self.run_cli("access-plan", "--spec", str(FIXTURE), "--output", str(output_path))
            plan = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(plan["gcp"]["project_roles"], ["roles/bigquery.resourceViewer", "roles/bigquery.user"])
        self.assertIn("ce:GetCostAndUsage", plan["aws"]["actions"])
        self.assertIn("cloudwatch:GetMetricData", plan["aws"]["actions"])
        self.assertFalse(plan["gcp"]["business_table_content_access"])
        self.assertFalse(plan["aws"]["cur"]["enabled"])


if __name__ == "__main__":
    unittest.main()

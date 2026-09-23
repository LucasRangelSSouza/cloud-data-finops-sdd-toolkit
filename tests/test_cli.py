import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "assessment.json"


class FinopsCliContractTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "cloud_data_finops.cli", *args],
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
        )

    def test_validate_accepts_the_declared_fixture_contract(self) -> None:
        completed = self.run_cli("validate", "--spec", str(FIXTURE))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("valid", completed.stdout)

    def test_preflight_rejects_owner_and_administrator_access(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["gcp"]["roles"].append("roles/owner")
        payload["aws"]["actions"].append("AdministratorAccess")

        with tempfile.TemporaryDirectory() as temporary_directory:
            unsafe_spec = Path(temporary_directory) / "unsafe.json"
            unsafe_spec.write_text(json.dumps(payload), encoding="utf-8")
            completed = self.run_cli("preflight", "--spec", str(unsafe_spec))

        self.assertEqual(completed.returncode, 2)
        self.assertIn("roles/owner", completed.stderr)
        self.assertIn("AdministratorAccess", completed.stderr)

    def test_preflight_rejects_a_cur_without_an_approved_prefix(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["aws"]["cur"] = {"enabled": True}

        with tempfile.TemporaryDirectory() as temporary_directory:
            unsafe_spec = Path(temporary_directory) / "unsafe-cur.json"
            unsafe_spec.write_text(json.dumps(payload), encoding="utf-8")
            completed = self.run_cli("preflight", "--spec", str(unsafe_spec))

        self.assertEqual(completed.returncode, 2)
        self.assertIn("approved_s3_prefix", completed.stderr)

    def test_report_writes_machine_readable_findings_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "report"
            completed = self.run_cli("report", "--spec", str(FIXTURE), "--output", str(output_directory))

            self.assertEqual(completed.returncode, 0, completed.stderr)
            findings = json.loads((output_directory / "findings.json").read_text(encoding="utf-8"))
            report = (output_directory / "report.md").read_text(encoding="utf-8")
            chart = output_directory / "cost-signals.png"

            self.assertTrue(chart.is_file())
            self.assertGreater(chart.stat().st_size, 1_000)

        self.assertEqual([finding["id"] for finding in findings], ["BQ-001", "AWS-001"])
        self.assertIn("Evidence and assumptions", report)
        self.assertIn("3,000 GB", report)


if __name__ == "__main__":
    unittest.main()

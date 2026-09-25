"""Spec and contract tests: incomplete specifications, malformed telemetry, and incomplete API responses."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cloud_data_finops.adapters import aws as aws_adapter
from cloud_data_finops.adapters import gcp as gcp_adapter
from cloud_data_finops.adapters.common import MAX_PAGES, AdapterResponseError
from cloud_data_finops.contracts import SpecificationError, TelemetryContractError, validate_specification, validate_telemetry_rows
from cloud_data_finops.workflow import AwsFixtureClient, GcpFixtureClient, collect_telemetry
from tests.helpers import ROOT, SENTINEL, job, load_fixture

PERIOD = {"start": "2026-08-02", "end": "2026-08-31"}


class PagedClient:
    """Returns a scripted sequence of pages regardless of the request."""

    def __init__(self, pages: list) -> None:
        self.pages = list(pages)

    def run_query(self, sql: str, *, purpose: str, page_token: str | None) -> object:
        return self.pages.pop(0) if self.pages else {"rows": [], "next_page_token": None}

    def call(self, operation: str, request: dict, *, page_token: str | None) -> object:
        return self.run_query("", purpose=operation, page_token=page_token)


class SpecificationContractTests(unittest.TestCase):
    def assert_rejected(self, specification: object, fragment: str) -> None:
        with self.assertRaises(SpecificationError) as context:
            validate_specification(specification)
        self.assertIn(fragment, str(context.exception))

    def test_fixture_is_valid(self) -> None:
        validate_specification(load_fixture())

    def test_missing_scope_period_or_acceptance_criteria_blocks_execution(self) -> None:
        for field in ("scope", "period", "acceptance_criteria", "gcp", "aws"):
            specification = load_fixture()
            del specification[field]
            self.assert_rejected(specification, field)

    def test_incomplete_scope_is_actionable(self) -> None:
        cases = [
            (("scope", "providers"), ["gcp"], "scope.providers"),
            (("scope", "allow_live_collection"), True, "allow_live_collection"),
            (("scope", "data_origin"), "production", "data_origin"),
            (("scope", "retention_days"), 0, "retention_days"),
            (("period", "start"), "2026-13", "period.start"),
            (("period", "start"), "2026-09-30", "period.start must not be after"),
            (("gcp", "project_id"), "", "gcp.project_id"),
            (("aws", "optional_telemetry"), ["billing_dump"], "unsupported entries: billing_dump"),
        ]
        for (section, key), value, fragment in cases:
            specification = load_fixture()
            specification[section][key] = value
            self.assert_rejected(specification, fragment)

    def test_empty_acceptance_criteria_are_rejected(self) -> None:
        specification = load_fixture()
        specification["acceptance_criteria"] = []
        self.assert_rejected(specification, "acceptance_criteria")

    def test_unknown_rules_and_thresholds_are_rejected(self) -> None:
        specification = load_fixture()
        specification["rules"] = {"enabled": ["BQ-999"]}
        self.assert_rejected(specification, "BQ-999")
        specification["rules"] = {"thresholds": {"BQ-001": {"bytes": 1}}}
        self.assert_rejected(specification, "rules.thresholds.BQ-001.bytes")
        specification["rules"] = {"thresholds": {"BQ-001": {"bytes_billed": -1}}}
        self.assert_rejected(specification, "non-negative")

    def test_unapproved_optional_telemetry_is_rejected(self) -> None:
        specification = load_fixture()
        specification["aws"]["optional_telemetry"] = ["commitment_coverage"]
        self.assert_rejected(specification, "aws.resources telemetry requires")
        specification = load_fixture()
        del specification["aws"]["cost_allocation_tag"]
        self.assert_rejected(specification, "aws.cost_allocation_tag")

    def test_non_object_root_is_rejected(self) -> None:
        self.assert_rejected([1, 2], "root must be an object")


class TelemetryContractTests(unittest.TestCase):
    def assert_safe_rejection(self, dataset: str, rows: object, fragment: str) -> None:
        with self.assertRaises(TelemetryContractError) as context:
            validate_telemetry_rows(dataset, rows)
        message = str(context.exception)
        self.assertIn(fragment, message)
        self.assertNotIn(SENTINEL, message)
        self.assertNotIn(SENTINEL, repr(context.exception.args))

    def test_malformed_rows_fail_without_echoing_values(self) -> None:
        bad_bytes = job()
        bad_bytes["bytes_billed"] = SENTINEL
        self.assert_safe_rejection("gcp.jobs", [bad_bytes], "gcp.jobs[0].bytes_billed: expected non-negative integer")
        negative = job()
        negative["bytes_billed"] = -5
        self.assert_safe_rejection("gcp.jobs", [negative], "bytes_billed")
        boolean = job()
        boolean["bytes_billed"] = True
        self.assert_safe_rejection("gcp.jobs", [boolean], "bytes_billed")
        self.assert_safe_rejection("gcp.jobs", [SENTINEL], "gcp.jobs[0]: expected an object")
        self.assert_safe_rejection("gcp.jobs", {"rows": SENTINEL}, "expected a list")
        cost = {"service": SENTINEL, "region": "us-east-1", "cost_usd": float("nan"), "baseline_usd": 1.0}
        self.assert_safe_rejection("aws.costs", [cost], "aws.costs[0].cost_usd")
        ratio = {"resource_id": SENTINEL, "type": "x", "utilization": 1.5, "observed_days": 30, "monthly_cost_usd": 1.0}
        self.assert_safe_rejection("aws.resources", [ratio], "utilization: expected number between 0 and 1")

    def test_missing_fields_are_named(self) -> None:
        row = job()
        del row["partition_pruned"]
        self.assert_safe_rejection("gcp.jobs", [row], "missing fields: partition_pruned")

    def test_inconsistent_rows_are_rejected(self) -> None:
        reservation = {"reservation_id": "r", "baseline_slots": 10, "avg_slots_used": 9.0, "peak_slots_used": 5.0, "hours_observed": 200}
        self.assert_safe_rejection("gcp.reservations", [reservation], "peak_slots_used")
        pruned_flat = job(partitioned=False, pruned=True)
        self.assert_safe_rejection("gcp.jobs", [pruned_flat], "requires references_partitioned_table")

    def test_extra_provider_fields_are_dropped(self) -> None:
        row = job()
        row["query_text"] = SENTINEL
        self.assertNotIn("query_text", validate_telemetry_rows("gcp.jobs", [row])[0])


class IncompleteApiResponseTests(unittest.TestCase):
    SCOPE = {"project_id": "demo-analytics"}

    def assert_incomplete(self, pages: list, fragment: str) -> None:
        with self.assertRaises(TelemetryContractError) as context:
            gcp_adapter.collect_job_metadata(self.SCOPE, PERIOD, PagedClient(pages))
        self.assertIn(fragment, str(context.exception))
        self.assertNotIn(SENTINEL, str(context.exception))

    def test_non_object_envelope(self) -> None:
        self.assert_incomplete([SENTINEL], "response envelope must be an object")
        with self.assertRaises(AdapterResponseError):
            gcp_adapter.collect_job_metadata(self.SCOPE, PERIOD, PagedClient([SENTINEL]))

    def test_missing_row_list(self) -> None:
        self.assert_incomplete([{"items": [SENTINEL]}], "incomplete response without a row list")

    def test_invalid_page_token(self) -> None:
        self.assert_incomplete([{"rows": [], "next_page_token": ""}], "next_page_token")

    def test_repeated_page_token(self) -> None:
        self.assert_incomplete([{"rows": [], "next_page_token": "a"}, {"rows": [], "next_page_token": "a"}], "page token repeated")

    def test_endless_pagination(self) -> None:
        pages = [{"rows": [], "next_page_token": f"t{index}"} for index in range(MAX_PAGES + 1)]
        self.assert_incomplete(pages, f"more than {MAX_PAGES} pages")

    def test_pages_are_joined_and_validated(self) -> None:
        pages = [{"rows": [job("a")], "next_page_token": "p2"}, {"rows": [job("b")], "next_page_token": None}]
        rows = gcp_adapter.collect_job_metadata(self.SCOPE, PERIOD, PagedClient(pages))
        self.assertEqual([row["job_id"] for row in rows], ["a", "b"])

    def test_malformed_row_on_a_later_page_fails_the_whole_collection(self) -> None:
        bad = job("b")
        bad["bytes_billed"] = SENTINEL
        pages = [{"rows": [job("a")], "next_page_token": "p2"}, {"rows": [bad], "next_page_token": None}]
        self.assert_incomplete(pages, "gcp.jobs[1].bytes_billed")

    def test_aws_incomplete_response(self) -> None:
        with self.assertRaisesRegex(AdapterResponseError, "aws:GetCostAndUsage: incomplete response"):
            aws_adapter.collect_cost_metadata({"account_alias": "demo"}, PERIOD, PagedClient([{"ResultsByTime": SENTINEL}]))

    def test_workflow_rejects_malformed_fixture_telemetry(self) -> None:
        specification = load_fixture()
        specification["aws"]["costs"][0]["cost_usd"] = SENTINEL
        with self.assertRaises(TelemetryContractError) as context:
            collect_telemetry(specification, GcpFixtureClient(specification["gcp"]), AwsFixtureClient(specification["aws"]))
        self.assertNotIn(SENTINEL, str(context.exception))


class CliFailSafeTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "cloud_data_finops.cli", *args], cwd=ROOT, check=False, text=True, capture_output=True)

    def test_report_rejects_malformed_telemetry_without_leaking_payload(self) -> None:
        specification = load_fixture()
        specification["gcp"]["jobs"][0]["bytes_billed"] = SENTINEL
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "malformed.json"
            path.write_text(json.dumps(specification), encoding="utf-8")
            completed = self.run_cli("report", "--spec", str(path), "--output", str(Path(directory) / "out"))
            self.assertFalse((Path(directory) / "out" / "findings.json").exists())
        self.assertEqual(completed.returncode, 3)
        self.assertIn("telemetry rejected: gcp.jobs[0].bytes_billed", completed.stderr)
        self.assertNotIn(SENTINEL, completed.stderr + completed.stdout)
        self.assertNotIn("Traceback", completed.stderr)

    def test_invalid_json_is_reported_without_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text('{"schema_version": "' + SENTINEL, encoding="utf-8")
            completed = self.run_cli("validate", "--spec", str(path))
        self.assertEqual(completed.returncode, 2)
        self.assertIn("invalid JSON", completed.stderr)
        self.assertNotIn(SENTINEL, completed.stderr)


if __name__ == "__main__":
    unittest.main()

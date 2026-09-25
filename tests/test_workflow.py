"""Integration: fixture -> collector -> policies -> findings -> Markdown report -> PPTX."""

import json
import tempfile
import unittest
from pathlib import Path

from pptx import Presentation

from cloud_data_finops.policies import evaluate
from cloud_data_finops.release import DECK_NAME, build_release
from cloud_data_finops.workflow import AwsFixtureClient, GcpFixtureClient, collect_fixture_telemetry, collect_telemetry
from tests.helpers import FIXTURE, load_fixture


class FixtureWorkflowTests(unittest.TestCase):
    def test_fixture_workflow_routes_metadata_through_both_provider_adapters(self) -> None:
        specification = load_fixture()
        gcp_client = GcpFixtureClient(specification["gcp"])
        aws_client = AwsFixtureClient(specification["aws"])

        collected = collect_telemetry(specification, gcp_client, aws_client)

        self.assertEqual(collected["gcp"]["jobs"], specification["gcp"]["jobs"])
        self.assertEqual(collected["aws"]["costs"], specification["aws"]["costs"])
        self.assertEqual([purpose for purpose, _ in gcp_client.queries], ["jobs", "schedules", "reservations"])
        self.assertEqual(aws_client.operations, ["GetCostAndUsage", "GetCostAndUsage", "GetMetricData", "GetSavingsPlansCoverage"])
        self.assertIsNot(collected, specification)

    def test_unapproved_optional_telemetry_is_not_collected(self) -> None:
        specification = load_fixture()
        specification["aws"]["optional_telemetry"] = []
        specification["aws"]["resources"] = []
        specification["aws"]["commitments"] = []
        collected = collect_fixture_telemetry(specification)
        rules = {finding["rule_id"] for finding in evaluate(collected)}
        self.assertNotIn("AWS-003", rules)
        self.assertNotIn("CMT-001", rules)

    def test_end_to_end_release_produces_every_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            findings = build_release(FIXTURE, output)
            written = json.loads((output / "findings.json").read_text(encoding="utf-8"))
            report = (output / "report.md").read_text(encoding="utf-8")
            deck = Presentation(str(output / DECK_NAME))
            self.assertTrue((output / "cost-signals.png").stat().st_size > 1_000)
            self.assertTrue((output / "access-plan.json").is_file())

        self.assertEqual(written, findings)
        self.assertEqual(len(findings), 11)
        for finding in findings:
            self.assertIn(f"### {finding['rule_id']} · {finding['subject']}", report)
        self.assertGreaterEqual(len(deck.slides), 6)


if __name__ == "__main__":
    unittest.main()

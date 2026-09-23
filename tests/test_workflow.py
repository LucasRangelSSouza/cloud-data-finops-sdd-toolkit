import json
from pathlib import Path
import unittest

from cloud_data_finops.workflow import collect_fixture_telemetry


FIXTURE = Path(__file__).parent / "fixtures" / "assessment.json"


class FixtureWorkflowTests(unittest.TestCase):
    def test_fixture_workflow_routes_metadata_through_both_provider_adapters(self) -> None:
        specification = json.loads(FIXTURE.read_text(encoding="utf-8"))

        collected = collect_fixture_telemetry(specification)

        self.assertEqual(collected["gcp"]["jobs"], specification["gcp"]["jobs"])
        self.assertEqual(collected["aws"]["costs"], specification["aws"]["costs"])
        self.assertIsNot(collected, specification)


if __name__ == "__main__":
    unittest.main()

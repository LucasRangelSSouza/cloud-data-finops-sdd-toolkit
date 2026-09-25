"""Regression: golden findings, report structure, deck outline, and byte-level determinism."""

import json
import tempfile
import unittest
from pathlib import Path

from cloud_data_finops.presentations import render_deck, slide_outline
from cloud_data_finops.release import DECK_NAME, MANIFEST, STRICT_ARTIFACTS, build_release, checksums, markdown_outline, parse_manifest
from tests.helpers import FIXTURE, GOLDEN, ROOT

EVIDENCE = ROOT / "docs" / "evidence" / "release-fixture"


class RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        cls.output = Path(cls.directory.name)
        cls.findings = build_release(FIXTURE, cls.output)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def golden(self, name: str) -> object:
        return json.loads((GOLDEN / name).read_text(encoding="utf-8"))

    def test_findings_match_the_golden_file(self) -> None:
        self.assertEqual(self.findings, self.golden("findings.json"))
        self.assertEqual((self.output / "findings.json").read_bytes(), (GOLDEN / "findings.json").read_bytes())

    def test_report_structure_matches_the_golden_outline(self) -> None:
        outline = markdown_outline((self.output / "report.md").read_text(encoding="utf-8"))
        self.assertEqual(outline, self.golden("report_outline.json"))

    def test_deck_outline_matches_the_golden_snapshot(self) -> None:
        self.assertEqual(slide_outline(self.output / DECK_NAME), self.golden("deck_outline.json"))

    def test_strict_artifacts_match_versioned_evidence_checksums(self) -> None:
        expected = parse_manifest((EVIDENCE / MANIFEST).read_text(encoding="utf-8"))
        actual = checksums(self.output)
        for name in STRICT_ARTIFACTS:
            self.assertEqual(actual[name], expected[name], name)

    def test_deck_rendering_is_byte_deterministic(self) -> None:
        from cloud_data_finops.workflow import collect_fixture_telemetry
        from tests.helpers import load_fixture

        telemetry = collect_fixture_telemetry(load_fixture())
        self.assertEqual(render_deck(telemetry, self.findings), render_deck(telemetry, self.findings))

    def test_second_build_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            build_release(FIXTURE, Path(directory))
            second = checksums(Path(directory))
        first = checksums(self.output)
        for name in STRICT_ARTIFACTS:
            self.assertEqual(first[name], second[name], name)


if __name__ == "__main__":
    unittest.main()

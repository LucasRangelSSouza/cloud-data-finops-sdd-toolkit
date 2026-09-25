"""Regenerate the fixture, golden snapshots, and versioned release evidence.

Run this only after an intentional change to rules, report layout, or deck
layout, then review the diff before committing it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cloud_data_finops.presentations import slide_outline  # noqa: E402
from cloud_data_finops.release import DECK_NAME, MANIFEST, build_release, checksums, markdown_outline, render_manifest  # noqa: E402
from cloud_data_finops.report import write_text  # noqa: E402
from cloud_data_finops.synthetic import render_assessment  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "assessment.json"
GOLDEN = ROOT / "tests" / "golden"
EVIDENCE = ROOT / "docs" / "evidence" / "release-fixture"


def main() -> int:
    write_text(FIXTURE, render_assessment())
    build_release(FIXTURE, EVIDENCE)
    GOLDEN.mkdir(parents=True, exist_ok=True)
    write_text(GOLDEN / "findings.json", (EVIDENCE / "findings.json").read_text(encoding="utf-8"))
    outline = markdown_outline((EVIDENCE / "report.md").read_text(encoding="utf-8"))
    write_text(GOLDEN / "report_outline.json", json.dumps(outline, indent=2) + "\n")
    write_text(GOLDEN / "deck_outline.json", json.dumps(slide_outline(EVIDENCE / DECK_NAME), indent=2, ensure_ascii=False) + "\n")
    write_text(EVIDENCE / MANIFEST, render_manifest(checksums(EVIDENCE)))
    print(f"updated {FIXTURE.relative_to(ROOT)}, {GOLDEN.relative_to(ROOT)}, and {EVIDENCE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

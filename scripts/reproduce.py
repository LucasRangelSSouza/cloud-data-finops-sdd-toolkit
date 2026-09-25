"""One-command reproduction: rebuild every artifact from the synthetic fixture and compare checksums.

Exit status 0 means the fixture matches the seeded generator and every strict
artifact matches docs/evidence/release-fixture/SHA256SUMS byte for byte.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cloud_data_finops.release import (  # noqa: E402
    INFORMATIONAL_ARTIFACTS,
    MANIFEST,
    STRICT_ARTIFACTS,
    build_release,
    checksums,
    parse_manifest,
)
from cloud_data_finops.synthetic import render_assessment  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "assessment.json"
EXPECTED = ROOT / "docs" / "evidence" / "release-fixture" / MANIFEST


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "reproduce")
    options = parser.parse_args()

    if FIXTURE.read_bytes() != render_assessment().encode("utf-8"):
        print("FAIL fixture: tests/fixtures/assessment.json differs from the seeded generator output", file=sys.stderr)
        return 1
    print("ok   fixture matches cloud_data_finops.synthetic (default seed)")

    findings = build_release(FIXTURE, options.output)
    expected = parse_manifest(EXPECTED.read_text(encoding="utf-8"))
    actual = checksums(options.output)
    failed = False
    for name in (*STRICT_ARTIFACTS, *INFORMATIONAL_ARTIFACTS):
        strict = name in STRICT_ARTIFACTS
        match = actual.get(name) == expected.get(name)
        label = "ok  " if match else ("FAIL" if strict else "note")
        print(f"{label} {name}  {actual.get(name, 'missing')}")
        failed |= strict and not match
    print(f"{len(findings)} findings written to {options.output}")
    if failed:
        print("strict artifact checksums differ; see docs/reproduce.md#troubleshooting", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

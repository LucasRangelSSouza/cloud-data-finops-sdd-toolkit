"""Release evidence: build every artifact from a specification and record SHA-256 checksums."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .access_plan import build_access_plan
from .contracts import load_specification
from .policies import evaluate
from .preflight import find_access_violations
from .presentations import write_deck
from .report import write_report, write_text
from .workflow import collect_fixture_telemetry

DECK_NAME = "synthetic-finops-assessment.pptx"
# The PNG depends on matplotlib's font rasterizer; its checksum is recorded but
# compared as informational, while every other artifact must match exactly.
STRICT_ARTIFACTS = ("access-plan.json", "findings.json", "report.md", DECK_NAME)
INFORMATIONAL_ARTIFACTS = ("cost-signals.png",)
MANIFEST = "SHA256SUMS"


def build_release(specification_path: Path, output: Path) -> list[dict[str, Any]]:
    specification = load_specification(specification_path)
    violations = find_access_violations(specification)
    if violations:
        raise ValueError("release blocked: " + "; ".join(violations))
    output.mkdir(parents=True, exist_ok=True)
    write_text(output / "access-plan.json", json.dumps(build_access_plan(specification), indent=2, sort_keys=True) + "\n")
    collected = collect_fixture_telemetry(specification)
    findings = evaluate(collected)
    write_report(output, collected, findings)
    write_deck(output / DECK_NAME, collected, findings)
    return findings


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checksums(output: Path) -> dict[str, str]:
    return {name: sha256(output / name) for name in (*STRICT_ARTIFACTS, *INFORMATIONAL_ARTIFACTS) if (output / name).is_file()}


def render_manifest(sums: dict[str, str]) -> str:
    return "".join(f"{digest}  {name}\n" for name, digest in sorted(sums.items()))


def parse_manifest(text: str) -> dict[str, str]:
    entries = {}
    for line in text.splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            entries[name.strip()] = digest
    return entries


def markdown_outline(markdown: str) -> list[str]:
    return [line for line in markdown.splitlines() if line.startswith("#")]

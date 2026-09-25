from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "assessment.json"
GOLDEN = ROOT / "tests" / "golden"
SENTINEL = "SENTINEL-PAYLOAD-7f3a"
GB = 10**9


def load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def empty_telemetry() -> dict[str, Any]:
    return {
        "gcp": {"jobs": [], "schedules": [], "reservations": []},
        "aws": {"costs": [], "tag_costs": [], "resources": [], "commitments": []},
        "assumptions": {},
    }


def job(job_id: str = "job", bytes_billed: int = GB, *, fingerprint: str | None = None, partitioned: bool = False, pruned: bool = False) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "fingerprint": fingerprint or f"fp-{job_id}",
        "bytes_billed": bytes_billed,
        "references_partitioned_table": partitioned,
        "partition_pruned": pruned,
        "scheduled": False,
    }


def with_rows(section: str, dataset: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    telemetry = empty_telemetry()
    telemetry[section][dataset] = deepcopy(rows)
    return telemetry

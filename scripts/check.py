from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "assessment.json"


def run(*command: str) -> None:
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode:
        raise SystemExit(completed.returncode)


run(sys.executable, "-m", "compileall", "-q", "cloud_data_finops", "tests")
run(sys.executable, "scripts/secret_scan.py")
run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v")
with tempfile.TemporaryDirectory() as output:
    run(sys.executable, "-m", "cloud_data_finops.cli", "validate", "--spec", str(FIXTURE))
    run(sys.executable, "-m", "cloud_data_finops.cli", "preflight", "--spec", str(FIXTURE))
    access_plan = Path(output) / "access-plan.json"
    run(sys.executable, "-m", "cloud_data_finops.cli", "access-plan", "--spec", str(FIXTURE), "--output", str(access_plan))
    run(sys.executable, "-m", "cloud_data_finops.cli", "report", "--spec", str(FIXTURE), "--output", output)
    if not access_plan.is_file():
        raise SystemExit("access-plan command did not produce access-plan.json")
    if not (Path(output) / "report.md").is_file():
        raise SystemExit("report command did not produce report.md")

"""Verification gate used by `make check` and CI.

Steps: format check, lint, compilation, secret scan, documentation links,
unit/contract/integration/regression tests, and a CLI smoke run over the
synthetic fixture. Any failing step stops the gate with its exit code.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "assessment.json"
LINT_TARGETS = ("cloud_data_finops", "tests", "scripts")


def run(label: str, *command: str) -> None:
    print(f"==> {label}", flush=True)
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def ruff_command() -> list[str]:
    if shutil.which("ruff"):
        return ["ruff"]
    probe = subprocess.run([sys.executable, "-m", "ruff", "--version"], capture_output=True, check=False)
    if probe.returncode == 0:
        return [sys.executable, "-m", "ruff"]
    raise SystemExit("ruff is not installed. Run: python -m pip install -r requirements-dev.txt")


def main() -> None:
    ruff = ruff_command()
    run("format check", *ruff, "format", "--check", *LINT_TARGETS)
    run("lint", *ruff, "check", *LINT_TARGETS)
    run("compile", sys.executable, "-m", "compileall", "-q", *LINT_TARGETS)
    run("secret scan", sys.executable, "scripts/secret_scan.py")
    run("documentation links", sys.executable, "scripts/check_links.py")
    run("tests", sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".")
    with tempfile.TemporaryDirectory() as output:
        cli = (sys.executable, "-m", "cloud_data_finops.cli")
        run("cli validate", *cli, "validate", "--spec", str(FIXTURE))
        run("cli preflight", *cli, "preflight", "--spec", str(FIXTURE), "--grants", str(ROOT / "tests" / "fixtures" / "grants" / "least-privilege.json"))
        run("cli access-plan", *cli, "access-plan", "--spec", str(FIXTURE), "--output", str(Path(output) / "access-plan.json"))
        run("cli report", *cli, "report", "--spec", str(FIXTURE), "--output", output)
        for name in ("access-plan.json", "findings.json", "report.md", "cost-signals.png", "synthetic-finops-assessment.pptx"):
            if not (Path(output) / name).is_file():
                raise SystemExit(f"CLI smoke run did not produce {name}")
    print("verification gate passed")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .access_plan import build_access_plan
from .contracts import SpecificationError, TelemetryContractError, load_specification
from .policies import evaluate
from .preflight import evaluate_grants, find_access_violations
from .presentations import write_deck
from .release import DECK_NAME
from .report import write_report, write_text
from .safety import SafetyViolation
from .synthetic import DEFAULT_SEED, render_assessment
from .workflow import collect_fixture_telemetry

EXIT_INVALID = 2
EXIT_REJECTED = 3


def parse_arguments(arguments: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="finops", description="Fixture-first GCP/AWS data FinOps assessment")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "preflight", "access-plan", "report", "deck"):
        subcommand = subcommands.add_parser(command)
        subcommand.add_argument("--spec", type=Path, required=True)
        if command in {"access-plan", "report", "deck"}:
            subcommand.add_argument("--output", type=Path, required=True)
        if command == "preflight":
            subcommand.add_argument("--grants", type=Path, help="provider-reported grants to compare with the approved request")
    synth = subcommands.add_parser("synth", help="write a synthetic assessment specification")
    synth.add_argument("--seed", type=int, default=DEFAULT_SEED)
    synth.add_argument("--output", type=Path, required=True)
    return parser.parse_args(arguments)


def _fail(prefix: str, messages: list[str], code: int = EXIT_INVALID) -> int:
    print(f"{prefix}: " + "; ".join(messages), file=sys.stderr)
    return code


def _preflight(options: argparse.Namespace, specification: dict) -> int:
    violations = find_access_violations(specification)
    if violations:
        return _fail("preflight failed", violations)
    if options.grants is not None:
        try:
            grants = json.loads(options.grants.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _fail("preflight failed", ["grants file is unreadable or is not valid JSON"])
        if not isinstance(grants, dict):
            return _fail("preflight failed", ["grants file root must be an object"])
        result = evaluate_grants(specification, grants)
        if result["violations"]:
            return _fail("preflight failed", result["violations"])
        if result["missing"]:
            return _fail("preflight incomplete", result["missing"])
    print("preflight passed")
    return 0


def _analyse(options: argparse.Namespace, specification: dict) -> int:
    collected = collect_fixture_telemetry(specification)
    findings = evaluate(collected)
    if options.command == "deck":
        write_deck(options.output, collected, findings)
        print(f"deck written to {options.output}")
        return 0
    write_report(options.output, collected, findings)
    write_deck(options.output / DECK_NAME, collected, findings)
    print(f"report written to {options.output}")
    return 0


def main(arguments: list[str] | None = None) -> int:
    options = parse_arguments(arguments)
    if options.command == "synth":
        options.output.parent.mkdir(parents=True, exist_ok=True)
        write_text(options.output, render_assessment(options.seed))
        print(f"synthetic specification written to {options.output}")
        return 0
    try:
        specification = load_specification(options.spec)
    except SpecificationError as error:
        return _fail("invalid specification", [str(error)])

    if options.command == "preflight":
        return _preflight(options, specification)
    violations = find_access_violations(specification)
    if options.command == "validate":
        if violations:
            return _fail("invalid specification", violations)
        print("valid specification")
        return 0
    if violations:
        return _fail(f"{options.command} blocked", violations)
    if options.command == "access-plan":
        options.output.parent.mkdir(parents=True, exist_ok=True)
        write_text(options.output, json.dumps(build_access_plan(specification), indent=2, sort_keys=True) + "\n")
        print(f"access plan written to {options.output}")
        return 0
    try:
        return _analyse(options, specification)
    except TelemetryContractError as error:
        return _fail("telemetry rejected", [str(error)], EXIT_REJECTED)
    except SafetyViolation as error:
        return _fail("request blocked", [str(error)], EXIT_REJECTED)


if __name__ == "__main__":
    raise SystemExit(main())

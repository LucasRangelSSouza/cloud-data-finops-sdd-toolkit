from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .access_plan import build_access_plan
from .contracts import SpecificationError, load_specification
from .policies import evaluate
from .preflight import find_access_violations
from .report import write_report
from .workflow import collect_fixture_telemetry


def parse_arguments(arguments: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="finops")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "preflight", "access-plan", "report"):
        subcommand = subcommands.add_parser(command)
        subcommand.add_argument("--spec", type=Path, required=True)
        if command in {"access-plan", "report"}:
            subcommand.add_argument("--output", type=Path, required=True)
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    options = parse_arguments(arguments)
    try:
        specification = load_specification(options.spec)
    except SpecificationError as error:
        print(f"invalid specification: {error}", file=sys.stderr)
        return 2

    violations = find_access_violations(specification)
    if options.command == "validate":
        if violations:
            print("invalid specification: " + "; ".join(violations), file=sys.stderr)
            return 2
        print("valid specification")
        return 0
    if options.command == "preflight":
        if violations:
            print("preflight failed: " + "; ".join(violations), file=sys.stderr)
            return 2
        print("preflight passed")
        return 0

    if options.command == "access-plan":
        if violations:
            print("access plan blocked: " + "; ".join(violations), file=sys.stderr)
            return 2
        options.output.parent.mkdir(parents=True, exist_ok=True)
        options.output.write_text(
            json.dumps(build_access_plan(specification), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"access plan written to {options.output}")
        return 0

    if violations:
        print("report blocked: " + "; ".join(violations), file=sys.stderr)
        return 2
    collected = collect_fixture_telemetry(specification)
    write_report(options.output, collected, evaluate(collected))
    print(f"report written to {options.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

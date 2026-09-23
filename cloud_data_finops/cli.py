from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .contracts import SpecificationError, load_specification
from .policies import evaluate
from .preflight import find_access_violations
from .report import write_report


def parse_arguments(arguments: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="finops")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "preflight", "report"):
        subcommand = subcommands.add_parser(command)
        subcommand.add_argument("--spec", type=Path, required=True)
        if command == "report":
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

    if violations:
        print("report blocked: " + "; ".join(violations), file=sys.stderr)
        return 2
    write_report(options.output, specification, evaluate(specification))
    print(f"report written to {options.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

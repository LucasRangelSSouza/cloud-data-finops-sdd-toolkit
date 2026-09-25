"""Check that relative links and images in Markdown files point to existing files.

External URLs (http, https, mailto) are not fetched, so the check runs offline.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRECTORIES = {".git", ".build", ".codex-finalizer", ".venv", "artifacts", "outputs", "node_modules", "__pycache__", ".ruff_cache"}
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"^(```|~~~)")


def markdown_files() -> list[Path]:
    return sorted(path for path in ROOT.rglob("*.md") if not any(part in EXCLUDED_DIRECTORIES for part in path.relative_to(ROOT).parts))


def broken_links(path: Path) -> list[str]:
    problems = []
    in_fence = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if FENCE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for target in LINK.findall(line):
            if re.match(r"^[a-z][a-z0-9+.\-]*:", target, re.IGNORECASE) or target.startswith("#"):
                continue
            relative = target.split("#", 1)[0]
            resolved = (path.parent / relative).resolve()
            if not resolved.exists():
                problems.append(f"{path.relative_to(ROOT)}:{number}: missing link target {target}")
    return problems


def main() -> int:
    files = markdown_files()
    problems = [problem for path in files for problem in broken_links(path)]
    if problems:
        print("documentation link check failed:\n" + "\n".join(problems), file=sys.stderr)
        return 1
    print(f"documentation link check passed ({len(files)} Markdown files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRECTORIES = {".git", ".build", ".codex-finalizer", "artifacts", "outputs", "node_modules", "__pycache__"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".yml", ".yaml", ".toml", ".txt"}
PATTERNS = {
    "Google service-account private key": re.compile(r"-----BEGIN PRIVATE KEY-----"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "GitHub personal token": re.compile(r"ghp_[A-Za-z0-9]{36}"),
}


def main() -> int:
    findings: list[str] = []
    for path in ROOT.rglob("*"):
        if any(part in EXCLUDED_DIRECTORIES for part in path.parts) or path.suffix not in TEXT_SUFFIXES:
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        for label, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{label}: {path.relative_to(ROOT)}")
    if findings:
        print("secret scan failed:\n" + "\n".join(findings), file=sys.stderr)
        return 1
    print("secret scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

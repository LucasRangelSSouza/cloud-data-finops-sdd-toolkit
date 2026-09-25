from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRECTORIES = {".git", ".build", ".codex-finalizer", ".venv", "artifacts", "outputs", "node_modules", "__pycache__", ".ruff_cache"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".yml", ".yaml", ".toml", ".txt", ".cfg", ".ini", ".env", ".mjs", ".js"}
TEXT_NAMES = {"Makefile", "SHA256SUMS", ".gitignore", ".gitattributes"}
PATTERNS = {
    "Google service-account private key": re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"(?:AKIA|ASIA)[0-9A-Z]{16}"),
    "GitHub personal token": re.compile(r"ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,}"),
    "API secret key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "Kaggle token assignment": re.compile(r"KAGGLE_API_TOKEN="),
    "Twelve-digit AWS account number in an ARN": re.compile(r"arn:aws:[a-z0-9\-]+:[a-z0-9\-]*:\d{12}:"),
}


def scanned_files() -> list[Path]:
    files = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_DIRECTORIES for part in relative.parts) or not path.is_file():
            continue
        if path.suffix in TEXT_SUFFIXES or path.name in TEXT_NAMES:
            files.append(path)
    return files


def main() -> int:
    findings: list[str] = []
    for path in scanned_files():
        if path.resolve() == Path(__file__).resolve():
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
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

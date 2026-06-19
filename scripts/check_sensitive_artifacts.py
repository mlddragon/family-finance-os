#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Iterable, List


BLOCKED_SUFFIXES = {
    ".csv",
    ".tsv",
    ".xlsx",
    ".xls",
    ".pdf",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".duckdb",
    ".parquet",
    ".feather",
}
BLOCKED_FILENAMES = {".env"}
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
}


@dataclass(frozen=True)
class Finding:
    path: Path
    reason: str


def _is_synthetic_fixture(path: Path) -> bool:
    parts = path.parts
    if "tests" not in parts or "fixtures" not in parts or "synthetic" not in parts:
        return False
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return "SYNTHETIC" in content[:2048]


def _is_blocked_file(path: Path) -> bool:
    if path.name == ".env.example":
        return False
    if path.name in BLOCKED_FILENAMES:
        return True
    return path.suffix.lower() in BLOCKED_SUFFIXES


def iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            yield path


def scan(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for path in iter_files(root):
        if not _is_blocked_file(path):
            continue
        if _is_synthetic_fixture(path):
            continue
        findings.append(Finding(path=path, reason="blocked sensitive artifact pattern"))
    return findings


def main(argv: List[str]) -> int:
    roots = [Path(arg).resolve() for arg in argv[1:]] or [Path.cwd()]
    findings: List[Finding] = []
    for root in roots:
        findings.extend(scan(root))

    if findings:
        print("Sensitive artifacts found:")
        for finding in findings:
            print(f"- {finding.path}: {finding.reason}")
        return 1

    print("No sensitive artifacts found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

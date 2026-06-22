#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Iterable


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
    "playwright-report",
    "test-results",
}

SKIP_FILENAMES = {
    "package-lock.json",
}

TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".conf",
    ".css",
    ".dockerignore",
    ".env",
    ".example",
    ".gitignore",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}

PLACEHOLDER_WORDS = {
    "changeme",
    "change-me",
    "dummy",
    "example",
    "fake",
    "placeholder",
    "redacted",
    "sample",
    "synthetic",
    "test",
    "todo",
    "your",
}

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private key block", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY-----")),
    ("aws access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("gitlab token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("openai api key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")),
    ("stripe secret key", re.compile(r"\b(?:sk|rk)_(?:live|test)_[0-9A-Za-z]{20,}\b")),
    (
        "secret assignment",
        re.compile(
            r'(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passphrase|private[_-]?key|secret|token)\b\s*[:=]\s*[\'\"]?([^\'\"\s#]{16,})'
        ),
    ),
)


@dataclass(frozen=True)
class Finding:
    path: Path
    line_number: int
    reason: str


def _is_placeholder(value: str) -> bool:
    normalized = value.lower()
    return any(word in normalized for word in PLACEHOLDER_WORDS)


def _is_text_candidate(path: Path) -> bool:
    if path.name in SKIP_FILENAMES:
        return False
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    return path.name in {"Dockerfile", "LICENSE", "NOTICE", "Makefile"}


def iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and _is_text_candidate(path):
            yield path


def scan_file(path: Path) -> list[Finding]:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []

    findings: list[Finding] = []
    for line_number, line in enumerate(lines, start=1):
        for reason, pattern in PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            value = match.group(1) if match.groups() else match.group(0)
            if _is_placeholder(value) or _is_placeholder(line):
                continue
            findings.append(Finding(path=path, line_number=line_number, reason=reason))
    return findings


def scan(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files(root):
        findings.extend(scan_file(path))
    return findings


def main(argv: list[str]) -> int:
    roots = [Path(arg).resolve() for arg in argv[1:]] or [Path.cwd().resolve()]
    findings: list[Finding] = []
    for root in roots:
        findings.extend(scan(root))

    if findings:
        print("Potential secrets found:")
        for finding in findings:
            print(f"- {finding.path}:{finding.line_number}: {finding.reason}")
        return 1

    print("No secret patterns found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

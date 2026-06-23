#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable


SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
}

RUNTIME_PATHS = (
    "apps/api",
    "apps/web/src",
    "Dockerfile",
    "docker-compose.yml",
    "pyproject.toml",
    "apps/web/package.json",
)

BANNED_RUNTIME_MARKERS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "api.openai.com",
    "api.anthropic.com",
    "plaid.com",
    "teller.io",
    "mx.com",
)

REQUIRED_DOCKERIGNORE_PATTERNS = (
    ".env",
    "*.csv",
    "*.xlsx",
    "*.pdf",
    "*.db",
    "*.sqlite",
    "raw",
    "reports",
    "exports",
)


def iter_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    for child in path.rglob("*"):
        if any(part in SKIP_DIRS for part in child.parts):
            continue
        if child.is_file():
            yield child


def fail(message: str) -> int:
    print(f"v1 security contract failed: {message}")
    return 1


def main(argv: list[str]) -> int:
    repo_root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd().resolve()
    compose = (repo_root / "docker-compose.yml").read_text()
    dockerfile = (repo_root / "Dockerfile").read_text()
    dockerignore = (repo_root / ".dockerignore").read_text()

    bind_patterns = (
        "127.0.0.1:${FFOS_HOST_PORT:-28080}:8080",
        "127.0.0.1:${FFOS_HOST_PORT:-${DILLON_FINANCES_HOST_PORT:-28080}}:8080",
    )
    if not any(pattern in compose for pattern in bind_patterns):
        return fail("Docker Compose must bind the browser app to 127.0.0.1 and default the personal host port to 28080.")
    if "APP_BIND_HOST: 127.0.0.1" not in compose:
        return fail("Docker Compose must keep APP_BIND_HOST at 127.0.0.1 by default.")
    for required in ("APP_ENV: ${APP_ENV:-personal}", "DATASET_KIND: ${DATASET_KIND:-personal}", "DEV_MODE: ${DEV_MODE:-false}"):
        if required not in compose:
            return fail(f"Docker Compose is missing runtime identity default: {required}")
    if "DATA_ROOT: /data" not in compose:
        return fail("Docker Compose must mount runtime state under /data.")
    if "USER 10001:10001" not in dockerfile:
        return fail("Docker runtime must use the non-root app user.")
    missing_patterns = [pattern for pattern in REQUIRED_DOCKERIGNORE_PATTERNS if pattern not in dockerignore]
    if missing_patterns:
        return fail(f".dockerignore is missing sensitive artifact patterns: {', '.join(missing_patterns)}")

    runtime_files: list[Path] = []
    for relative_path in RUNTIME_PATHS:
        runtime_files.extend(iter_files(repo_root / relative_path))
    for path in runtime_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in BANNED_RUNTIME_MARKERS:
            if marker in text:
                return fail(f"runtime file {path.relative_to(repo_root)} contains networked/secret marker {marker}")

    print("v1 security contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

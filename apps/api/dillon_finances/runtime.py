from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional


REQUIRED_DATA_ROOT_DIRS = (
    "inbox",
    "raw",
    "processed",
    "quarantine",
    "database",
    "reports",
    "monthly_close",
    "exports",
    "logs",
)


class DataRootConfigurationError(RuntimeError):
    """Raised when local financial data would be stored in an unsafe location."""


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def find_repo_root(start: Optional[Path] = None) -> Optional[Path]:
    current = (start or Path.cwd()).resolve()
    candidates: Iterable[Path] = (current, *current.parents)
    for candidate in candidates:
        if (candidate / ".git").exists():
            return candidate
    return None


def validate_data_root(data_root: Path, *, repo_root: Optional[Path] = None) -> Path:
    resolved_data_root = data_root.expanduser().resolve()
    resolved_repo_root = repo_root.resolve() if repo_root else find_repo_root()

    if resolved_repo_root and (
        resolved_data_root == resolved_repo_root
        or _is_relative_to(resolved_data_root, resolved_repo_root)
    ):
        raise DataRootConfigurationError(
            "DATA_ROOT must be outside the git repository for financial data safety."
        )

    return resolved_data_root


def bootstrap_data_root(data_root: Path, *, repo_root: Optional[Path] = None) -> Path:
    resolved_data_root = validate_data_root(data_root, repo_root=repo_root)
    resolved_data_root.mkdir(parents=True, exist_ok=True)
    for directory in REQUIRED_DATA_ROOT_DIRS:
        (resolved_data_root / directory).mkdir(parents=True, exist_ok=True)
    return resolved_data_root

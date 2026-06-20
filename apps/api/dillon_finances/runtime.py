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


def _ensure_safe_child_directory(data_root: Path, directory_name: str) -> None:
    directory = data_root / directory_name
    if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
        raise DataRootConfigurationError(
            f"DATA_ROOT/{directory_name} must be a safe directory inside DATA_ROOT."
        )
    directory.mkdir(exist_ok=True)
    if directory.is_symlink() or not directory.resolve().is_relative_to(data_root):
        raise DataRootConfigurationError(
            f"DATA_ROOT/{directory_name} must be a safe directory inside DATA_ROOT."
        )


def bootstrap_data_root(data_root: Path, *, repo_root: Optional[Path] = None) -> Path:
    resolved_data_root = validate_data_root(data_root, repo_root=repo_root)
    resolved_data_root.mkdir(parents=True, exist_ok=True)
    for directory in REQUIRED_DATA_ROOT_DIRS:
        _ensure_safe_child_directory(resolved_data_root, directory)
    return resolved_data_root

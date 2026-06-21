from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
from typing import Iterable, Optional


SYNTHETIC_ARTIFACT_MARKER = "QA synthetic demo - not real financial data"

ALLOWED_APP_ENVS = {"personal", "qa"}
ALLOWED_DATASET_KINDS = {"personal", "synthetic"}

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
    "manifests",
)


class DataRootConfigurationError(RuntimeError):
    """Raised when local financial data would be stored in an unsafe location."""


class RuntimeEnvironmentConfigurationError(RuntimeError):
    """Raised when runtime environment identity is invalid or unsafe."""


@dataclass(frozen=True)
class RuntimeEnvironment:
    app_env: str
    app_env_label: str
    dataset_kind: str
    dev_mode: bool

    @property
    def qa_controls_enabled(self) -> bool:
        return self.app_env == "qa" and self.dataset_kind == "synthetic" and self.dev_mode

    @property
    def synthetic_artifact_marker(self) -> Optional[str]:
        if self.dataset_kind == "synthetic":
            return SYNTHETIC_ARTIFACT_MARKER
        return None

    def to_status_fields(self) -> dict[str, object]:
        return {
            **asdict(self),
            "qa_controls_enabled": self.qa_controls_enabled,
        }


def _bool_from_env(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def runtime_environment_from_env() -> RuntimeEnvironment:
    app_env = os.environ.get("APP_ENV", "personal").strip().lower()
    if app_env not in ALLOWED_APP_ENVS:
        raise RuntimeEnvironmentConfigurationError(
            f"APP_ENV must be one of: {', '.join(sorted(ALLOWED_APP_ENVS))}."
        )

    dataset_kind_default = "synthetic" if app_env == "qa" else "personal"
    dataset_kind = os.environ.get("DATASET_KIND", dataset_kind_default).strip().lower()
    if dataset_kind not in ALLOWED_DATASET_KINDS:
        raise RuntimeEnvironmentConfigurationError(
            f"DATASET_KIND must be one of: {', '.join(sorted(ALLOWED_DATASET_KINDS))}."
        )

    default_label = "QA synthetic demo" if app_env == "qa" else "Personal data"
    app_env_label = os.environ.get("APP_ENV_LABEL", default_label).strip() or default_label
    return RuntimeEnvironment(
        app_env=app_env,
        app_env_label=app_env_label,
        dataset_kind=dataset_kind,
        dev_mode=_bool_from_env(os.environ.get("DEV_MODE", "false")),
    )


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

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

from dillon_finances.runtime import REQUIRED_DATA_ROOT_DIRS, validate_data_root


RESET_CONFIRMATION = "RESET QA DATA"


class QaResetError(RuntimeError):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _personal_default_path() -> Path:
    return (Path.home() / "Dillon_Finances_Data").expanduser().resolve()


def reset_qa_data_root(
    *,
    data_root: Path,
    app_env: str,
    dataset_kind: str,
    confirmation: str,
) -> Path:
    if confirmation != RESET_CONFIRMATION:
        raise QaResetError(f'QA reset requires exact confirmation: "{RESET_CONFIRMATION}".')
    if app_env != "qa" or dataset_kind != "synthetic":
        raise QaResetError("QA reset is allowed only for QA/synthetic environment identity.")

    resolved_data_root = validate_data_root(data_root, repo_root=_repo_root())
    if resolved_data_root == _personal_default_path():
        raise QaResetError("QA reset refuses the personal default data root.")

    if resolved_data_root.exists():
        shutil.rmtree(resolved_data_root)
    resolved_data_root.mkdir(parents=True, exist_ok=True)
    for directory_name in REQUIRED_DATA_ROOT_DIRS:
        (resolved_data_root / directory_name).mkdir(exist_ok=True)
    return resolved_data_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset the local QA synthetic data root.")
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()

    try:
        reset_qa_data_root(
            data_root=args.data_root,
            app_env=os.environ.get("APP_ENV", ""),
            dataset_kind=os.environ.get("DATASET_KIND", ""),
            confirmation=args.confirm,
        )
    except QaResetError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import os
from pathlib import Path

from family_finance_os.qa_ops import RESET_CONFIRMATION, QaOpsError, QaResetError, reset_qa_data_root


__all__ = ["RESET_CONFIRMATION", "QaResetError", "reset_qa_data_root"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


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
            repo_root=_repo_root(),
        )
    except QaOpsError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

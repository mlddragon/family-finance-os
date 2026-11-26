"""Resolution and materialization of synthetic QA template assets.

Synthetic templates are committed to git under ``tests/fixtures/synthetic`` and copied
into the container image at build time. Runtime code never reads them from the installed
package; QA seeding copies the files it needs into ``DATA_ROOT`` first (Decision 16, #106).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


QA_ASSET_ROOT_ENV = "QA_ASSET_ROOT"
VENDOR_COLLECT_PREFIX = "vendor_collect_"
VENDOR_FIXTURE_GLOB = "vendor_*.json"
VENDOR_SYNTHETIC_SUBDIR = ("vendor_scrapes", "synthetic")
IMPORT_PACK_SUBDIR = "imports"


class QaAssetError(RuntimeError):
    """Raised when synthetic QA templates cannot be located."""


def _repo_asset_root() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "synthetic"


def qa_asset_root() -> Path:
    """Return the directory holding synthetic QA templates.

    ``QA_ASSET_ROOT`` is set by the container image. On a developer host the repository
    checkout is used instead.
    """
    configured = os.environ.get(QA_ASSET_ROOT_ENV, "").strip()
    if configured:
        root = Path(configured).expanduser().resolve()
        if not root.is_dir():
            raise QaAssetError(f"{QA_ASSET_ROOT_ENV} is set to '{root}' but that directory does not exist.")
        return root

    repo_root = _repo_asset_root()
    if repo_root.is_dir():
        return repo_root

    raise QaAssetError(
        "Synthetic QA templates were not found. Set "
        f"{QA_ASSET_ROOT_ENV} to a directory containing the synthetic template pack."
    )


def read_qa_asset(relative_path: str) -> str:
    path = qa_asset_root() / relative_path
    if not path.is_file():
        raise QaAssetError(
            f"Synthetic QA template '{relative_path}' is missing from {qa_asset_root()}. "
            "Run `make generate-synthetic-imports` if this is an import pack file."
        )
    return path.read_text(encoding="utf-8")


def read_import_pack_asset(filename: str) -> str:
    return read_qa_asset(f"{IMPORT_PACK_SUBDIR}/{filename}")


def vendor_synthetic_fixture_dir(data_root: Path) -> Path:
    return data_root.joinpath(*VENDOR_SYNTHETIC_SUBDIR)


def materialize_vendor_synthetic_fixtures(data_root: Path) -> list[Path]:
    """Copy vendor scrape templates into ``DATA_ROOT`` so synthetic runs work in Docker."""
    target_dir = vendor_synthetic_fixture_dir(data_root)
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for source_path in sorted(qa_asset_root().glob(VENDOR_FIXTURE_GLOB)):
        target_path = target_dir / source_path.name
        shutil.copyfile(source_path, target_path)
        written.append(target_path)
    if not written:
        raise QaAssetError(
            f"No vendor scrape templates matching '{VENDOR_FIXTURE_GLOB}' were found in {qa_asset_root()}."
        )
    return written

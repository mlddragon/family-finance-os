from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from family_finance_os.main import create_app
from family_finance_os.source_profiles import list_source_profiles


IMPORT_PACK_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic" / "imports"
EXPECTED_LEDGER_FILES = (
    "alliant_checking.csv",
    "alliant_savings.csv",
    "alliant_credit_card.csv",
    "chase_prime_visa.csv",
    "chase_prime_visa_stale.csv",
)
MIN_LEDGER_ROWS = {
    "alliant_checking.csv": 10,
    "alliant_savings.csv": 6,
    "alliant_credit_card.csv": 10,
    "chase_prime_visa.csv": 12,
}


def _row_count(path: Path) -> int:
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return max(len(lines) - 1, 0)


def test_synthetic_import_pack_files_exist_with_minimum_row_counts():
    manifest_path = IMPORT_PACK_DIR / "manifest.json"
    assert manifest_path.exists(), "Run `make generate-synthetic-imports` to create the import pack."

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "SYNTHETIC" in manifest["synthetic_fixture_marker"]

    for filename in EXPECTED_LEDGER_FILES:
        path = IMPORT_PACK_DIR / filename
        assert path.exists(), filename
        assert _row_count(path) >= MIN_LEDGER_ROWS.get(filename, 1), filename

    assert _row_count(IMPORT_PACK_DIR / "net_worth.csv") >= 6
    assert _row_count(IMPORT_PACK_DIR / "receipts.csv") >= 6
    assert (IMPORT_PACK_DIR / "blocked_wrong_header.csv").exists()


def test_synthetic_import_pack_validates_through_api(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    profiles_by_key = {profile.source_key: profile for profile in list_source_profiles()}

    with TestClient(app) as client:
        for filename in EXPECTED_LEDGER_FILES[:4]:
            if filename == "chase_prime_visa_stale.csv":
                continue
            source_key = filename.removesuffix(".csv")
            profile = profiles_by_key[source_key]
            content = (IMPORT_PACK_DIR / filename).read_text(encoding="utf-8")
            header = content.strip().splitlines()[0].split(",")
            allowed_headers = set(profile.expected_headers) | set(profile.optional_headers)
            assert all(column in allowed_headers for column in header)
            assert list(profile.expected_headers) == [column for column in header if column in profile.expected_headers]

            upload = client.post(
                "/api/uploads",
                data={"source_key": source_key},
                files={"file": (f"SYNTHETIC_{filename}", content, "text/csv")},
            )
            assert upload.status_code == 200, upload.text
            batch_id = upload.json()["import_batch"]["id"]
            validation = client.post(f"/api/import-batches/{batch_id}/validate", json={})
            assert validation.status_code == 200, validation.text
            assert validation.json()["validation_status"] == "passed"
            assert validation.json()["findings"] == []

            accept = client.post(
                f"/api/import-batches/{batch_id}/accept",
                json={"acknowledge_warnings": True},
            )
            assert accept.status_code == 200, accept.text

        transactions = client.get("/api/transactions")
        assert transactions.status_code == 200
        assert len(transactions.json()["transactions"]) >= 40

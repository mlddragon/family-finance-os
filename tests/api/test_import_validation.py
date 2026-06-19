from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from dillon_finances.import_validation import VALIDATION_CODES
from dillon_finances.main import create_app


CHASE_HEADER = "Transaction Date,Post Date,Description,Category,Amount\n"


def fresh_chase_row(amount: str = "12.34") -> str:
    transaction_date = date.today() - timedelta(days=1)
    post_date = date.today()
    return (
        f"{transaction_date.isoformat()},{post_date.isoformat()},"
        f"SYNTHETIC GROCERY,Food,{amount}\n"
    )


def stale_chase_row() -> str:
    transaction_date = date.today() - timedelta(days=60)
    post_date = transaction_date + timedelta(days=1)
    return (
        f"{transaction_date.isoformat()},{post_date.isoformat()},"
        "SYNTHETIC OLD GROCERY,Food,12.34\n"
    )


def write_inbox_file(data_root: Path, filename: str, content: str) -> Path:
    inbox_path = data_root / "inbox" / filename
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    inbox_path.write_text(content)
    return inbox_path


def test_validation_code_registry_covers_pr5_required_codes():
    assert {
        "file_missing",
        "file_unreadable",
        "file_empty",
        "unsupported_file_type",
        "schema_mismatch",
        "ambiguous_source",
        "source_account_unconfirmed",
        "date_parse_failed",
        "amount_parse_failed",
        "amount_precision_invalid",
        "amount_sign_unexpected",
        "row_count_mismatch",
        "duplicate_imported_row",
        "duplicate_canonical_candidate",
        "overlapping_export",
        "source_stale",
        "required_source_missing",
        "batch_validation_incomplete",
    }.issubset(VALIDATION_CODES)


def test_inbox_scan_validate_and_accept_synthetic_file_preserves_raw(tmp_path):
    write_inbox_file(
        tmp_path,
        "SYNTHETIC_chase_prime_visa.csv",
        CHASE_HEADER + fresh_chase_row(),
    )
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        scan_response = client.post("/api/inbox/scan")
        assert scan_response.status_code == 200
        batch_id = scan_response.json()["import_batches"][0]["id"]

        validate_response = client.post(f"/api/import-batches/{batch_id}/validate")
        assert validate_response.status_code == 200
        assert validate_response.json()["findings"] == []

        accept_response = client.post(f"/api/import-batches/{batch_id}/accept")
        assert accept_response.status_code == 200
        accepted_body = accept_response.json()

    assert accepted_body["status"] == "accepted"
    raw_path = Path(accepted_body["source_files"][0]["stored_path"])
    assert raw_path.exists()
    assert raw_path.is_relative_to(tmp_path / "raw")
    assert raw_path.read_text().startswith(CHASE_HEADER)


def test_blocking_validation_prevents_accept_and_quarantines_file(tmp_path):
    write_inbox_file(
        tmp_path,
        "SYNTHETIC_chase_wrong_header.csv",
        "Wrong,Header\n2026-06-01,12.34\n",
    )
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        batch_id = client.post("/api/inbox/scan").json()["import_batches"][0]["id"]
        validate_response = client.post(f"/api/import-batches/{batch_id}/validate")
        assert validate_response.status_code == 200
        assert validate_response.json()["findings"][0]["code"] == "schema_mismatch"

        accept_response = client.post(f"/api/import-batches/{batch_id}/accept")
        assert accept_response.status_code == 409
        assert accept_response.json()["detail"]["code"] == "blocking_validation_findings"

    quarantine_files = list((tmp_path / "quarantine").glob("**/SYNTHETIC_chase_wrong_header.csv"))
    reason_files = list((tmp_path / "quarantine").glob("**/*.reason.json"))
    assert quarantine_files
    assert reason_files


def test_warnings_require_acknowledgment_before_accept(tmp_path):
    content = CHASE_HEADER + fresh_chase_row()
    write_inbox_file(tmp_path, "SYNTHETIC_chase_prime_visa_one.csv", content)
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        first_batch_id = client.post("/api/inbox/scan").json()["import_batches"][0]["id"]
        client.post(f"/api/import-batches/{first_batch_id}/validate")
        client.post(f"/api/import-batches/{first_batch_id}/accept")

        write_inbox_file(tmp_path, "SYNTHETIC_chase_prime_visa_two.csv", content)
        second_batch_id = client.post("/api/inbox/scan").json()["import_batches"][-1]["id"]
        validate_response = client.post(f"/api/import-batches/{second_batch_id}/validate")
        assert any(
            finding["severity"] == "warning" and finding["code"] == "overlapping_export"
            for finding in validate_response.json()["findings"]
        )

        blocked_accept = client.post(f"/api/import-batches/{second_batch_id}/accept")
        assert blocked_accept.status_code == 409
        assert blocked_accept.json()["detail"]["code"] == "warning_acknowledgment_required"

        acknowledged_accept = client.post(
            f"/api/import-batches/{second_batch_id}/accept",
            json={"acknowledge_warnings": True},
        )
        assert acknowledged_accept.status_code == 200
        assert acknowledged_accept.json()["status"] == "accepted"


def test_upload_rejects_unsupported_file_type(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        response = client.post(
            "/api/uploads",
            files={"file": ("statement.pdf", b"not a ledger csv", "application/pdf")},
        )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "unsupported_file_type"


def test_validation_findings_endpoint_lists_current_findings(tmp_path):
    write_inbox_file(
        tmp_path,
        "SYNTHETIC_bad_amount.csv",
        CHASE_HEADER + fresh_chase_row("not-money"),
    )
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        batch_id = client.post("/api/inbox/scan").json()["import_batches"][0]["id"]
        client.post(f"/api/import-batches/{batch_id}/validate")
        response = client.get("/api/validation-findings")

    assert response.status_code == 200
    assert response.json()["findings"][0]["code"] == "amount_parse_failed"


def test_missing_file_creates_blocking_finding(tmp_path):
    path = write_inbox_file(
        tmp_path,
        "SYNTHETIC_missing_after_scan.csv",
        CHASE_HEADER + fresh_chase_row(),
    )
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        batch_id = client.post("/api/inbox/scan").json()["import_batches"][0]["id"]
        path.unlink()
        response = client.post(f"/api/import-batches/{batch_id}/validate")

    assert response.status_code == 200
    assert response.json()["findings"][0]["severity"] == "blocking"
    assert response.json()["findings"][0]["code"] == "file_missing"


def test_empty_file_creates_blocking_finding(tmp_path):
    write_inbox_file(tmp_path, "SYNTHETIC_empty.csv", "")
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        batch_id = client.post("/api/inbox/scan").json()["import_batches"][0]["id"]
        response = client.post(f"/api/import-batches/{batch_id}/validate")

    assert response.status_code == 200
    assert response.json()["findings"][0]["severity"] == "blocking"
    assert response.json()["findings"][0]["code"] == "file_empty"


def test_unsupported_inbox_file_creates_blocking_finding(tmp_path):
    write_inbox_file(tmp_path, "SYNTHETIC_statement.xlsx", "not a csv ledger export")
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        batch_id = client.post("/api/inbox/scan").json()["import_batches"][0]["id"]
        response = client.post(f"/api/import-batches/{batch_id}/validate")

    assert response.status_code == 200
    assert response.json()["findings"][0]["severity"] == "blocking"
    assert response.json()["findings"][0]["code"] == "unsupported_file_type"


def test_malformed_date_creates_blocking_finding(tmp_path):
    write_inbox_file(
        tmp_path,
        "SYNTHETIC_bad_date.csv",
        CHASE_HEADER + "not-a-date,2026-06-02,SYNTHETIC GROCERY,Food,12.34\n",
    )
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        batch_id = client.post("/api/inbox/scan").json()["import_batches"][0]["id"]
        response = client.post(f"/api/import-batches/{batch_id}/validate")

    assert response.status_code == 200
    assert response.json()["findings"][0]["severity"] == "blocking"
    assert response.json()["findings"][0]["code"] == "date_parse_failed"


def test_stale_source_creates_warning_finding(tmp_path):
    write_inbox_file(
        tmp_path,
        "SYNTHETIC_stale.csv",
        CHASE_HEADER + stale_chase_row(),
    )
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        batch_id = client.post("/api/inbox/scan").json()["import_batches"][0]["id"]
        response = client.post(f"/api/import-batches/{batch_id}/validate")

    assert response.status_code == 200
    assert response.json()["findings"][0]["severity"] == "warning"
    assert response.json()["findings"][0]["code"] == "source_stale"


def test_duplicate_file_hash_warns_without_silent_dedupe(tmp_path):
    content = CHASE_HEADER + fresh_chase_row()
    write_inbox_file(tmp_path, "SYNTHETIC_duplicate_one.csv", content)
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        first_batch_id = client.post("/api/inbox/scan").json()["import_batches"][0]["id"]
        client.post(f"/api/import-batches/{first_batch_id}/validate")
        client.post(f"/api/import-batches/{first_batch_id}/accept")

        write_inbox_file(tmp_path, "SYNTHETIC_duplicate_two.csv", content)
        second_batch_id = client.post("/api/inbox/scan").json()["import_batches"][-1]["id"]
        validate_response = client.post(f"/api/import-batches/{second_batch_id}/validate")
        finding_codes = {finding["code"] for finding in validate_response.json()["findings"]}

        accept_response = client.post(
            f"/api/import-batches/{second_batch_id}/accept",
            json={"acknowledge_warnings": True},
        )

    assert {"duplicate_imported_row", "overlapping_export"}.issubset(finding_codes)
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "accepted"
    assert Path(accept_response.json()["source_files"][0]["stored_path"]).exists()


def test_accepted_file_is_removed_from_inbox_after_raw_preservation(tmp_path):
    inbox_file = write_inbox_file(
        tmp_path,
        "SYNTHETIC_accept_once.csv",
        CHASE_HEADER + fresh_chase_row(),
    )
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        batch_id = client.post("/api/inbox/scan").json()["import_batches"][0]["id"]
        client.post(f"/api/import-batches/{batch_id}/validate")
        client.post(f"/api/import-batches/{batch_id}/accept")
        scan_again_response = client.post("/api/inbox/scan")

    assert not inbox_file.exists()
    assert [batch["id"] for batch in scan_again_response.json()["import_batches"]] == []


def test_quarantined_file_is_removed_from_inbox(tmp_path):
    inbox_file = write_inbox_file(
        tmp_path,
        "SYNTHETIC_quarantine_once.csv",
        "Wrong,Header\n2026-06-01,12.34\n",
    )
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        batch_id = client.post("/api/inbox/scan").json()["import_batches"][0]["id"]
        client.post(f"/api/import-batches/{batch_id}/validate")
        client.post(f"/api/import-batches/{batch_id}/accept")
        scan_again_response = client.post("/api/inbox/scan")

    assert not inbox_file.exists()
    assert [batch["id"] for batch in scan_again_response.json()["import_batches"]] == []

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any


SOURCE_FIXTURES = (
    "v1_valid_alliant_checking.csv",
    "v1_valid_alliant_savings.csv",
    "v1_valid_alliant_credit_card.csv",
    "v1_valid_chase_prime_visa.csv",
)


class E2EError(RuntimeError):
    pass


class E2EHttpError(E2EError):
    def __init__(self, method: str, path: str, status_code: int, detail: str):
        super().__init__(f"{method} {path} failed with HTTP {status_code}: {detail}")
        self.method = method
        self.path = path
        self.status_code = status_code
        self.detail = detail


def render_fixture(path: Path) -> str:
    fresh_date = date.today() - timedelta(days=1)
    fresh_post_date = date.today()
    text = path.read_text()
    return text.replace("{{FRESH_DATE}}", fresh_date.isoformat()).replace(
        "{{FRESH_POST_DATE}}", fresh_post_date.isoformat()
    )


def request_json(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise E2EHttpError(method, path, exc.code, detail) from exc


def wait_for_status(base_url: str) -> dict[str, Any]:
    last_error: Exception | None = None
    for _ in range(30):
        try:
            status = request_json(base_url, "GET", "/api/status")
            if status.get("local_only") is True:
                return status
        except Exception as exc:  # noqa: BLE001 - surfaced after retry window
            last_error = exc
        time.sleep(1)
    raise E2EError(f"app did not become ready: {last_error}")


def write_source_fixtures(repo_root: Path, data_root: Path) -> None:
    fixture_dir = repo_root / "tests/fixtures/synthetic"
    inbox = data_root / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    for fixture_name in SOURCE_FIXTURES:
        (inbox / fixture_name).write_text(render_fixture(fixture_dir / fixture_name))


def assert_condition(condition: bool, message: str) -> None:
    if not condition:
        raise E2EError(message)


def save_decision(base_url: str, transaction_id: str, *, field_name: str, decision_type: str, value: object) -> None:
    request_json(
        base_url,
        "POST",
        "/api/decision-events",
        {
            "target_type": "canonical_transaction",
            "target_id": transaction_id,
            "decision_type": decision_type,
            "field_name": field_name,
            "proposed_value": value,
            "approved_value": value,
            "actor": "owner",
            "suggestion_source": "owner",
            "explicit_user_action": True,
        },
    )


def confirm_source_profiles(base_url: str, source_keys: list[str]) -> None:
    request_json(
        base_url,
        "PATCH",
        "/api/settings",
        {
            "actor": "owner",
            "changes": [
                {
                    "domain": "sources",
                    "setting_key": f"sources.{source_key}.profile_confirmation_status",
                    "value": "owner_confirmed_header_sample",
                    "note": f"SYNTHETIC Docker E2E header-only sample confirmation for {source_key}.",
                }
                for source_key in sorted(source_keys)
            ],
        },
    )


def run_blocked_validation_path(base_url: str, data_root: Path) -> dict[str, Any]:
    blocked_filename = "SYNTHETIC_docker_blocked_wrong_header.csv"
    blocked_path = data_root / "inbox" / blocked_filename
    blocked_path.parent.mkdir(parents=True, exist_ok=True)
    blocked_path.write_text("Wrong,Header\nSYNTHETIC BLOCKED,1.23\n")

    scan = request_json(base_url, "POST", "/api/inbox/scan")
    matching_batches = [
        batch
        for batch in scan["import_batches"]
        if any(
            source_file.get("original_filename") == blocked_filename
            for source_file in batch.get("source_files", [])
        )
    ]
    assert_condition(len(matching_batches) == 1, "blocked wrong-header file must scan as one batch")
    batch_id = matching_batches[0]["id"]

    validation = request_json(base_url, "POST", f"/api/import-batches/{batch_id}/validate")
    validation_codes = sorted({finding["code"] for finding in validation["findings"]})
    blocking = [finding for finding in validation["findings"] if finding["severity"] == "blocking"]
    assert_condition("schema_mismatch" in validation_codes, "blocked path must report schema_mismatch")
    assert_condition(blocking, "blocked path must report at least one blocking finding")

    try:
        request_json(base_url, "POST", f"/api/import-batches/{batch_id}/accept")
    except E2EHttpError as exc:
        assert_condition(exc.status_code == 409, "blocked path accept must fail with HTTP 409")
    else:
        raise E2EError("blocked path accept unexpectedly succeeded")

    findings = request_json(base_url, "GET", "/api/validation-findings")
    assert_condition(
        any(
            finding["status"] == "open"
            and finding["severity"] == "blocking"
            and finding["code"] == "schema_mismatch"
            for finding in findings["findings"]
        ),
        "blocked path must leave an open schema_mismatch validation finding",
    )
    return {"blocked_batch_id": batch_id, "validation_codes": validation_codes}


def run_closed_loop(base_url: str, repo_root: Path, data_root: Path) -> dict[str, Any]:
    status = wait_for_status(base_url)
    assert_condition(status["local_only"] is True, "status must report local-only mode")
    assert_condition(status["bind_host"] == "127.0.0.1", "status must report localhost bind")
    assert_condition(status["app_env"] == "qa", "Docker E2E must run against QA runtime identity")
    assert_condition(status["dataset_kind"] == "synthetic", "Docker E2E must run against synthetic dataset identity")
    write_source_fixtures(repo_root, data_root)

    scan = request_json(base_url, "POST", "/api/inbox/scan")
    assert_condition(len(scan["import_batches"]) == len(SOURCE_FIXTURES), "all synthetic source files must scan")
    accepted_source_keys: list[str] = []
    for batch in scan["import_batches"]:
        validation = request_json(base_url, "POST", f"/api/import-batches/{batch['id']}/validate")
        blocking = [finding for finding in validation["findings"] if finding["severity"] == "blocking"]
        assert_condition(not blocking, f"batch {batch['id']} has blocking findings")
        accepted_batch = request_json(
            base_url,
            "POST",
            f"/api/import-batches/{batch['id']}/accept",
            {"acknowledge_warnings": False},
        )
        accepted_source_keys.append(accepted_batch["source_key"])

    confirm_source_profiles(base_url, accepted_source_keys)

    transactions = request_json(base_url, "GET", "/api/transactions")["transactions"]
    assert_condition(len(transactions) >= 4, "closed loop must create synthetic transactions")
    save_decision(base_url, transactions[0]["id"], field_name="category", decision_type="category_change", value="business")
    for transaction in transactions:
        save_decision(
            base_url,
            transaction["id"],
            field_name="review_status",
            decision_type="review_status_change",
            value="reviewed",
        )

    reports = request_json(base_url, "POST", "/api/reports/run", {"actor": "owner"})
    draft_close = request_json(base_url, "POST", "/api/monthly-close/draft", {"actor": "owner"})
    final_close = request_json(
        base_url,
        "POST",
        "/api/monthly-close/finalize",
        {"actor": "owner", "notes": "SYNTHETIC Docker E2E final close."},
    )
    advisor = request_json(base_url, "POST", "/api/exports/advisor", {"actor": "owner"})
    summary = request_json(base_url, "GET", "/api/operator-summary")
    blocked_path = run_blocked_validation_path(base_url, data_root)

    assert_condition(reports["report_run"]["status"] == "completed", "reports must complete")
    assert_condition(draft_close["monthly_close"]["status"] == "draft", "draft close must be created")
    assert_condition(final_close["monthly_close"]["status"] == "final", "final close must be created")
    assert_condition(final_close["monthly_close"]["provisional"] is False, "final close must not be provisional")
    assert_condition(advisor["artifacts"], "advisor export must produce artifacts")
    assert_condition(summary["next_action"]["code"] == "refresh_source_data", "next action must advance to refresh")
    return {
        "accepted_sources": summary["sources"]["imported_source_keys"],
        "transaction_count": summary["review"]["total_transactions"],
        "artifact_count": summary["artifacts"]["generated_count"],
        "blocked_path": blocked_path,
        "monthly_close_status": summary["monthly_close"]["status"],
        "next_action": summary["next_action"]["code"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the synthetic Docker E2E closed loop.")
    parser.add_argument("--base-url", default="http://127.0.0.1:28081")
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()

    result = run_closed_loop(args.base_url, Path(args.repo_root).resolve(), Path(args.data_root).resolve())
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

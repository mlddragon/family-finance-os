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
        raise E2EError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc


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
            "actor": "mason",
            "suggestion_source": "owner",
            "explicit_user_action": True,
        },
    )


def run_closed_loop(base_url: str, repo_root: Path, data_root: Path) -> dict[str, Any]:
    status = wait_for_status(base_url)
    assert_condition(status["local_only"] is True, "status must report local-only mode")
    assert_condition(status["bind_host"] == "127.0.0.1", "status must report localhost bind")
    write_source_fixtures(repo_root, data_root)

    scan = request_json(base_url, "POST", "/api/inbox/scan")
    assert_condition(len(scan["import_batches"]) == len(SOURCE_FIXTURES), "all synthetic source files must scan")
    for batch in scan["import_batches"]:
        validation = request_json(base_url, "POST", f"/api/import-batches/{batch['id']}/validate")
        blocking = [finding for finding in validation["findings"] if finding["severity"] == "blocking"]
        assert_condition(not blocking, f"batch {batch['id']} has blocking findings")
        request_json(base_url, "POST", f"/api/import-batches/{batch['id']}/accept", {"acknowledge_warnings": False})

    transactions = request_json(base_url, "GET", "/api/transactions")["transactions"]
    assert_condition(len(transactions) >= 4, "closed loop must create synthetic transactions")
    save_decision(base_url, transactions[0]["id"], field_name="category", decision_type="category_change", value="Groceries")
    for transaction in transactions:
        save_decision(
            base_url,
            transaction["id"],
            field_name="review_status",
            decision_type="review_status_change",
            value="reviewed",
        )

    reports = request_json(base_url, "POST", "/api/reports/run", {"actor": "mason"})
    draft_close = request_json(base_url, "POST", "/api/monthly-close/draft", {"actor": "mason"})
    final_close = request_json(
        base_url,
        "POST",
        "/api/monthly-close/finalize",
        {"actor": "mason", "notes": "SYNTHETIC Docker E2E final close."},
    )
    advisor = request_json(base_url, "POST", "/api/exports/advisor", {"actor": "mason"})
    summary = request_json(base_url, "GET", "/api/operator-summary")

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
        "monthly_close_status": summary["monthly_close"]["status"],
        "next_action": summary["next_action"]["code"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v1 synthetic Docker E2E closed loop.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()

    result = run_closed_loop(args.base_url, Path(args.repo_root).resolve(), Path(args.data_root).resolve())
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

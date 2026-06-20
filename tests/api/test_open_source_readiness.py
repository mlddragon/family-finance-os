from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from dillon_finances.main import create_app


CHASE_HEADER = "Transaction Date,Post Date,Description,Category,Amount\n"


def fresh_row(description: str = "SYNTHETIC GROCERY", amount: str = "12.34") -> str:
    transaction_date = date.today() - timedelta(days=1)
    post_date = date.today()
    return (
        f"{transaction_date.isoformat()},{post_date.isoformat()},"
        f"{description},Food,{amount}\n"
    )


def write_inbox_file(data_root: Path, filename: str, content: str) -> None:
    inbox_path = data_root / "inbox" / filename
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    inbox_path.write_text(content)


def accept_chase_batch(client: TestClient, data_root: Path) -> dict:
    write_inbox_file(
        data_root,
        "SYNTHETIC_open_source_readiness.csv",
        CHASE_HEADER + fresh_row("SYNTHETIC GROCERY", "12.34"),
    )
    batch_id = client.post("/api/inbox/scan").json()["import_batches"][-1]["id"]
    assert client.post(f"/api/import-batches/{batch_id}/validate").status_code == 200
    response = client.post(f"/api/import-batches/{batch_id}/accept")
    assert response.status_code == 200
    return response.json()


def test_fresh_install_uses_generic_branding_and_no_required_source_defaults(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        status = client.get("/api/status").json()
        settings = client.get("/api/settings").json()
        summary = client.get("/api/operator-summary").json()
        findings = client.get("/api/validation-findings").json()["findings"]

    assert status["app"] == "Family Finance OS"
    setting_by_key = {
        (setting["domain"], setting["setting_key"]): setting["value"]
        for setting in settings["settings"]
    }
    assert setting_by_key[("branding", "branding.app_display_name")] == "Family Finance OS"
    assert setting_by_key[("household", "household.display_name")] == "Household"
    assert setting_by_key[("operator", "operator.default_actor")] == "owner"
    assert setting_by_key[("locale", "locale.default_locale")] == "en-US"
    assert setting_by_key[("locale", "locale.currency_code")] == "USD"
    assert setting_by_key[("sources", "sources.chase_prime_visa.enabled")] is False
    assert setting_by_key[("reports", "reports.monthly_close.title_template")] == (
        "{app_name} Monthly Close - {month}"
    )
    assert {profile["source_key"] for profile in settings["source_profiles"]} == {
        "alliant_checking",
        "alliant_savings",
        "alliant_credit_card",
        "chase_prime_visa",
    }
    assert all(profile["is_template"] is True for profile in settings["source_profiles"])
    assert all(profile["required"] is False for profile in settings["source_profiles"])
    assert all(profile["enabled"] is False for profile in settings["source_profiles"])
    assert summary["sources"]["required_count"] == 0
    assert not [finding for finding in findings if finding["code"] == "required_source_missing"]


def test_existing_source_required_setting_is_preserved_across_reseed(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        assert client.get("/api/settings").status_code == 200
        patch = client.patch(
            "/api/settings",
            json={
                "actor": "mason",
                "changes": [
                    {
                        "domain": "sources",
                        "setting_key": "sources.chase_prime_visa.required",
                        "value": True,
                        "note": "Synthetic test preserves an existing enabled required source.",
                    }
                ],
            },
        )
        assert patch.status_code == 200

    replacement_app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    with TestClient(replacement_app) as client:
        settings = client.get("/api/settings").json()

    chase_profile = next(
        profile for profile in settings["source_profiles"] if profile["source_key"] == "chase_prime_visa"
    )
    assert chase_profile["required"] is True
    assert chase_profile["enabled"] is True


def test_category_catalog_has_stable_system_keys_and_custom_category_path(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        categories = client.get("/api/categories")
        missing_note = client.post(
            "/api/categories",
            json={"display_name": "Family Project", "actor": "mason"},
        )
        custom = client.post(
            "/api/categories",
            json={
                "display_name": "Family Project",
                "aliases": ["House project"],
                "actor": "mason",
                "note": "Synthetic custom category for install-specific work.",
            },
        )
        renamed = client.patch(
            "/api/categories/groceries",
            json={
                "display_name": "Groceries & Staples",
                "aliases": ["Food"],
                "actor": "mason",
                "note": "Synthetic display rename; stable key must remain groceries.",
            },
        )

    assert categories.status_code == 200
    category_keys = {category["category_key"] for category in categories.json()["categories"]}
    assert {"income", "groceries", "business", "uncategorized"}.issubset(category_keys)
    assert "jillybean" not in category_keys
    assert "mason_hustle" not in category_keys
    assert missing_note.status_code == 422
    assert missing_note.json()["detail"]["code"] == "category_note_required"
    assert custom.status_code == 200
    assert custom.json()["category"]["category_key"] == "family_project"
    assert custom.json()["category"]["category_type"] == "custom"
    assert renamed.status_code == 200
    assert renamed.json()["category"]["category_key"] == "groceries"
    assert renamed.json()["category"]["display_name"] == "Groceries & Staples"
    assert renamed.json()["category"]["aliases"] == ["Food"]


def test_category_decision_uses_stable_key_and_exposes_display_fields(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        accept_chase_batch(client, tmp_path)
        transaction = client.get("/api/transactions").json()["transactions"][0]
        response = client.post(
            "/api/decision-events",
            json={
                "target_type": "canonical_transaction",
                "target_id": transaction["id"],
                "decision_type": "category_change",
                "field_name": "category",
                "proposed_value": "business",
                "approved_value": "business",
                "actor": "mason",
                "suggestion_source": "owner",
                "explicit_user_action": True,
            },
        )
        detail = client.get(f"/api/transactions/{transaction['id']}").json()["transaction"]

    assert response.status_code == 200
    assert detail["category_key_current"] == "business"
    assert detail["category_display_name_current"] == "Business"
    assert detail["category_current"] == "Business"


def test_report_memo_uses_configurable_generic_branding(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        accept_chase_batch(client, tmp_path)
        client.patch(
            "/api/settings",
            json={
                "actor": "mason",
                "changes": [
                    {
                        "domain": "branding",
                        "setting_key": "branding.app_display_name",
                        "value": "Open Household Ledger",
                    }
                ],
            },
        )
        response = client.post("/api/monthly-close/draft", json={"actor": "mason"})

    assert response.status_code == 200
    memo_artifact = next(
        artifact for artifact in response.json()["artifacts"] if artifact["artifact_type"] == "monthly_close_memo"
    )
    assert Path(memo_artifact["path"]).read_text().startswith("# Open Household Ledger Monthly Close - ")

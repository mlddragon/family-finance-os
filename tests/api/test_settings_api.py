from sqlalchemy import select

from fastapi.testclient import TestClient

from family_finance_os.database import create_sqlite_engine
from family_finance_os.main import create_app
from family_finance_os.models import Setting, SettingEvent


def test_get_settings_seeds_sqlite_settings_and_source_profiles(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    client = TestClient(app)

    response = client.get("/api/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["data_root"]["path"] == str(tmp_path.resolve())
    assert body["local_only"] is True
    assert body["tabs"] == [
        "Branding",
        "Data root",
        "Sources",
        "Categories",
        "Locale",
        "Operator",
        "Thresholds",
        "Reports",
        "Privacy",
        "Future integrations",
    ]
    assert {profile["source_key"] for profile in body["source_profiles"]} == {
        "alliant_checking",
        "alliant_savings",
        "alliant_credit_card",
        "chase_prime_visa",
    }
    assert any(
        setting["domain"] == "branding"
        and setting["setting_key"] == "branding.app_display_name"
        and setting["friendly_name"] == "App display name"
        and setting["value"] == "Family Finance OS"
        and setting["default_value"] == "Family Finance OS"
        and setting["changed_from_default"] is False
        for setting in body["settings"]
    )
    assert any(
        setting["domain"] == "operator"
        and setting["setting_key"] == "operator.default_actor"
        and setting["value"] == "owner"
        for setting in body["settings"]
    )
    assert any(
        setting["domain"] == "freshness"
        and setting["setting_key"] == "sources.chase_prime_visa.freshness_threshold_days"
        and setting["value"] == 14
        for setting in body["settings"]
    )
    assert any(
        setting["domain"] == "sources"
        and setting["setting_key"] == "sources.chase_prime_visa.enabled"
        and setting["value"] is False
        for setting in body["settings"]
    )
    chase_profile = next(
        profile for profile in body["source_profiles"] if profile["source_key"] == "chase_prime_visa"
    )
    assert chase_profile["is_template"] is True
    assert chase_profile["enabled"] is False
    assert chase_profile["template_required_default"] is False
    assert chase_profile["required"] is False

    engine = create_sqlite_engine(tmp_path / "database" / "family_finance_os.sqlite3")
    with engine.connect() as connection:
        assert connection.execute(select(Setting)).first() is not None


def test_patch_settings_updates_value_and_appends_event(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    client = TestClient(app)
    client.get("/api/settings")

    response = client.patch(
        "/api/settings",
        json={
            "actor": "mason",
            "changes": [
                {
                    "domain": "freshness",
                    "setting_key": "sources.chase_prime_visa.freshness_threshold_days",
                    "value": 21,
                    "note": "Synthetic threshold adjustment for test.",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    changed_setting = next(
        setting
        for setting in body["settings"]
        if setting["setting_key"] == "sources.chase_prime_visa.freshness_threshold_days"
    )
    assert changed_setting["friendly_name"] == "Chase Prime Visa freshness threshold"
    assert changed_setting["default_value"] == 14
    assert changed_setting["changed_from_default"] is True
    assert body["events"][0]["previous_value"] == 14
    assert body["events"][0]["new_value"] == 21

    engine = create_sqlite_engine(tmp_path / "database" / "family_finance_os.sqlite3")
    with engine.connect() as connection:
        events = connection.execute(select(SettingEvent)).all()
        setting_value = connection.execute(
            select(Setting.value_json).where(
                Setting.setting_key == "sources.chase_prime_visa.freshness_threshold_days"
            )
        ).scalar_one()

    assert len(events) == 1
    assert setting_value == "21"


def test_patch_settings_rejects_invalid_freshness_threshold(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    client = TestClient(app)
    client.get("/api/settings")

    response = client.patch(
        "/api/settings",
        json={
            "actor": "mason",
            "changes": [
                {
                    "domain": "freshness",
                    "setting_key": "sources.chase_prime_visa.freshness_threshold_days",
                    "value": 0,
                }
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "invalid_freshness_threshold"


def test_high_impact_setting_change_requires_note(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    client = TestClient(app)
    client.get("/api/settings")

    response = client.patch(
        "/api/settings",
        json={
            "actor": "mason",
            "changes": [
                {
                    "domain": "sources",
                    "setting_key": "sources.chase_prime_visa.required",
                    "value": True,
                }
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "high_impact_note_required"

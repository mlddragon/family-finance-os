from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from dillon_finances.models import Setting, SettingEvent
from dillon_finances.source_profiles import iter_source_profiles, list_source_profiles


SETTINGS_TABS = [
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

SOURCE_PROFILE_CONFIRMATION_STATUSES = {
    "pending_owner_sample",
    "owner_confirmed_header_sample",
    "owner_confirmed_sanitized_sample",
}

CONFIRMED_SOURCE_PROFILE_STATUSES = {
    "owner_confirmed_header_sample",
    "owner_confirmed_sanitized_sample",
}


class SettingsValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class SettingChange(BaseModel):
    domain: str
    setting_key: str
    value: Any
    note: Optional[str] = None


class SettingsPatchRequest(BaseModel):
    actor: str = Field(min_length=1)
    changes: list[SettingChange] = Field(min_length=1)


def _dump_value(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _load_value(value_json: str) -> Any:
    return json.loads(value_json)


def default_settings() -> list[dict[str, Any]]:
    settings: list[dict[str, Any]] = [
        {
            "domain": "branding",
            "setting_key": "branding.app_display_name",
            "value": "Family Finance OS",
            "editable": True,
            "note_required": False,
        },
        {
            "domain": "household",
            "setting_key": "household.display_name",
            "value": "Household",
            "editable": True,
            "note_required": False,
        },
        {
            "domain": "operator",
            "setting_key": "operator.default_actor",
            "value": "owner",
            "editable": True,
            "note_required": False,
        },
        {
            "domain": "locale",
            "setting_key": "locale.default_locale",
            "value": "en-US",
            "editable": True,
            "note_required": False,
        },
        {
            "domain": "locale",
            "setting_key": "locale.currency_code",
            "value": "USD",
            "editable": True,
            "note_required": False,
        },
        {
            "domain": "privacy",
            "setting_key": "runtime.local_only",
            "value": True,
            "editable": False,
            "note_required": True,
        },
        {
            "domain": "reports",
            "setting_key": "monthly_close.requires_all_required_sources",
            "value": True,
            "editable": False,
            "note_required": True,
        },
        {
            "domain": "reports",
            "setting_key": "reports.monthly_close.title_template",
            "value": "{app_name} Monthly Close - {month}",
            "editable": True,
            "note_required": False,
        },
        {
            "domain": "reports",
            "setting_key": "reports.advisor_export.title_template",
            "value": "{app_name} Advisor Export - {month}",
            "editable": True,
            "note_required": False,
        },
        {
            "domain": "future_integrations",
            "setting_key": "vendor_enrichment.status",
            "value": "deferred",
            "editable": False,
            "note_required": True,
        },
        {
            "domain": "future_integrations",
            "setting_key": "ai_integration.status",
            "value": "disabled",
            "editable": False,
            "note_required": True,
        },
    ]

    for profile in iter_source_profiles():
        settings.extend(
            [
                {
                    "domain": "sources",
                    "setting_key": f"sources.{profile.source_key}.display_name",
                    "value": profile.display_name,
                    "editable": True,
                    "note_required": False,
                },
                {
                    "domain": "sources",
                    "setting_key": f"sources.{profile.source_key}.required",
                    "value": profile.required,
                    "editable": True,
                    "note_required": True,
                },
                {
                    "domain": "sources",
                    "setting_key": f"sources.{profile.source_key}.enabled",
                    "value": profile.required,
                    "editable": True,
                    "note_required": True,
                },
                {
                    "domain": "freshness",
                    "setting_key": f"sources.{profile.source_key}.freshness_threshold_days",
                    "value": profile.freshness_threshold_days,
                    "editable": True,
                    "note_required": False,
                },
                {
                    "domain": "sources",
                    "setting_key": f"sources.{profile.source_key}.profile_confirmation_status",
                    "value": profile.confirmation_status,
                    "editable": True,
                    "note_required": True,
                },
            ]
        )

    return settings


def seed_default_settings(session: Session) -> None:
    for default in default_settings():
        existing = session.scalar(
            select(Setting).where(
                Setting.domain == default["domain"],
                Setting.setting_key == default["setting_key"],
            )
        )
        if existing is None:
            session.add(
                Setting(
                    domain=default["domain"],
                    setting_key=default["setting_key"],
                    value_json=_dump_value(default["value"]),
                )
            )
    session.commit()


def _setting_metadata(domain: str, setting_key: str) -> dict[str, Any]:
    for setting in default_settings():
        if setting["domain"] == domain and setting["setting_key"] == setting_key:
            return setting
    raise SettingsValidationError("unknown_setting", f"Unknown setting: {domain}.{setting_key}")


def _validate_change(change: SettingChange, existing: Setting) -> None:
    metadata = _setting_metadata(change.domain, change.setting_key)

    if not metadata["editable"]:
        raise SettingsValidationError(
            "setting_read_only",
            f"{change.setting_key} is read-only for v1.",
        )

    if change.domain == "freshness":
        if not isinstance(change.value, int) or not 1 <= change.value <= 365:
            raise SettingsValidationError(
                "invalid_freshness_threshold",
                "Freshness thresholds must be an integer from 1 to 365 days.",
            )

    if change.domain in {"branding", "household"}:
        if not isinstance(change.value, str) or not change.value.strip() or len(change.value.strip()) > 120:
            raise SettingsValidationError(
                "invalid_display_setting",
                "Display settings must be non-empty text of 120 characters or fewer.",
            )

    if change.domain == "operator" and change.setting_key == "operator.default_actor":
        if not isinstance(change.value, str) or not change.value.strip() or len(change.value.strip()) > 80:
            raise SettingsValidationError(
                "invalid_actor_setting",
                "Default actor must be non-empty text of 80 characters or fewer.",
            )

    if change.domain == "locale" and change.setting_key == "locale.default_locale":
        if change.value != "en-US":
            raise SettingsValidationError(
                "unsupported_locale",
                "Only en-US is supported by the maintained v0.2 locale bundle.",
            )

    if change.domain == "locale" and change.setting_key == "locale.currency_code":
        if not isinstance(change.value, str) or not re.fullmatch(r"[A-Z]{3}", change.value):
            raise SettingsValidationError(
                "invalid_currency_code",
                "Currency code must be a three-letter ISO-style uppercase code.",
            )

    if change.domain == "reports" and change.setting_key.endswith(".title_template"):
        if not isinstance(change.value, str) or "{month}" not in change.value or len(change.value) > 200:
            raise SettingsValidationError(
                "invalid_report_title_template",
                "Report title templates must include {month} and be 200 characters or fewer.",
            )

    if change.domain == "sources" and change.setting_key.endswith(".profile_confirmation_status"):
        if change.value not in SOURCE_PROFILE_CONFIRMATION_STATUSES:
            raise SettingsValidationError(
                "invalid_source_profile_confirmation",
                "Source profile confirmation must use an approved v1 status.",
            )

    if change.domain == "sources" and (
        change.setting_key.endswith(".required") or change.setting_key.endswith(".enabled")
    ):
        if not isinstance(change.value, bool):
            raise SettingsValidationError(
                "invalid_source_boolean_setting",
                "Source enabled and required settings must be boolean values.",
            )

    previous_value = _load_value(existing.value_json)
    note_required = bool(metadata["note_required"])
    materially_relaxed_freshness = (
        change.domain == "freshness"
        and isinstance(previous_value, int)
        and isinstance(change.value, int)
        and change.value > previous_value
        and change.value - previous_value >= 30
    )
    changing_source_coverage = (
        change.domain == "sources"
        and (change.setting_key.endswith(".required") or change.setting_key.endswith(".enabled"))
        and isinstance(previous_value, bool)
        and isinstance(change.value, bool)
        and previous_value != change.value
    )

    if (note_required or materially_relaxed_freshness or changing_source_coverage) and not (
        change.note and change.note.strip()
    ):
        raise SettingsValidationError(
            "high_impact_note_required",
            "High-impact settings changes require an owner note.",
        )


def list_settings(session: Session) -> list[dict[str, Any]]:
    records = session.scalars(select(Setting).order_by(Setting.domain, Setting.setting_key)).all()
    return [
        {
            "id": record.id,
            "domain": record.domain,
            "setting_key": record.setting_key,
            "value": _load_value(record.value_json),
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            **{
                key: value
                for key, value in _setting_metadata(record.domain, record.setting_key).items()
                if key not in {"domain", "setting_key", "value"}
            },
        }
        for record in records
    ]


def list_settings_events(session: Session) -> list[dict[str, Any]]:
    records = session.scalars(select(SettingEvent).order_by(SettingEvent.created_at)).all()
    return [
        {
            "id": record.id,
            "domain": record.domain,
            "setting_key": record.setting_key,
            "previous_value": _load_value(record.previous_value_json)
            if record.previous_value_json is not None
            else None,
            "new_value": _load_value(record.new_value_json),
            "actor": record.actor,
            "notes": record.notes,
            "created_at": record.created_at,
        }
        for record in records
    ]


def apply_settings_patch(session: Session, patch: SettingsPatchRequest) -> list[SettingEvent]:
    events: list[SettingEvent] = []
    for change in patch.changes:
        existing = session.scalar(
            select(Setting).where(
                Setting.domain == change.domain,
                Setting.setting_key == change.setting_key,
            )
        )
        if existing is None:
            raise SettingsValidationError(
                "unknown_setting",
                f"Unknown setting: {change.domain}.{change.setting_key}",
            )

        _validate_change(change, existing)
        previous_value_json = existing.value_json
        new_value_json = _dump_value(change.value)
        existing.value_json = new_value_json
        event = SettingEvent(
            setting=existing,
            domain=change.domain,
            setting_key=change.setting_key,
            previous_value_json=previous_value_json,
            new_value_json=new_value_json,
            actor=patch.actor,
            notes=change.note,
            validation_result_json=_dump_value({"status": "passed"}),
        )
        session.add(event)
        events.append(event)

    session.commit()
    return events


def settings_payload(
    session: Session,
    *,
    data_root: Path,
    local_only: bool,
) -> dict[str, Any]:
    seed_default_settings(session)
    settings_by_key = {
        (setting.domain, setting.setting_key): _load_value(setting.value_json)
        for setting in session.scalars(select(Setting)).all()
    }
    return {
        "tabs": SETTINGS_TABS,
        "local_only": local_only,
        "data_root": {
            "path": str(data_root),
            "exists": data_root.exists(),
        },
        "settings": list_settings(session),
        "settings_events": list_settings_events(session),
        "source_profiles": [
            {
                **profile.to_dict(),
                "display_name": settings_by_key.get(
                    ("sources", f"sources.{profile.source_key}.display_name"),
                    profile.display_name,
                ),
                "required": settings_by_key.get(
                    ("sources", f"sources.{profile.source_key}.required"),
                    profile.required,
                ),
                "freshness_threshold_days": settings_by_key.get(
                    ("freshness", f"sources.{profile.source_key}.freshness_threshold_days"),
                    profile.freshness_threshold_days,
                ),
                "confirmation_status": settings_by_key.get(
                    ("sources", f"sources.{profile.source_key}.profile_confirmation_status"),
                    profile.confirmation_status,
                ),
                "is_template": True,
                "enabled": bool(
                    settings_by_key.get(
                        ("sources", f"sources.{profile.source_key}.enabled"),
                        profile.required,
                    )
                    or settings_by_key.get(
                        ("sources", f"sources.{profile.source_key}.required"),
                        profile.required,
                    )
                ),
                "template_required_default": profile.required,
            }
            for profile in list_source_profiles()
        ],
    }


def serialize_events(events: Iterable[SettingEvent]) -> list[dict[str, Any]]:
    return [
        {
            "id": event.id,
            "domain": event.domain,
            "setting_key": event.setting_key,
            "previous_value": _load_value(event.previous_value_json)
            if event.previous_value_json is not None
            else None,
            "new_value": _load_value(event.new_value_json),
            "actor": event.actor,
            "notes": event.notes,
            "created_at": event.created_at,
        }
        for event in events
    ]

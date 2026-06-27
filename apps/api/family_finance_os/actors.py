from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field


class ActorContext(BaseModel):
    actor_key: str = Field(min_length=1)
    actor_type: str = Field(pattern="^(human|system)$")
    display_name: str = Field(min_length=1)
    persona_key: Optional[str] = None
    persona_label: Optional[str] = None
    group_keys: list[str] = Field(default_factory=list)
    system_persona_key: Optional[str] = None
    source: str = Field(pattern="^(local_selector|system|compat_actor_string|auth_session|recovery|dev_bypass)$")


GROUPS = [
    {"group_key": "administrator", "display_name": "Administrator"},
    {"group_key": "finance_manager", "display_name": "Finance Manager"},
    {"group_key": "finance_contributor", "display_name": "Finance Contributor"},
    {"group_key": "financial_analyst", "display_name": "Financial Analyst"},
    {"group_key": "report_viewer", "display_name": "Report Viewer"},
]

HUMAN_ACTORS = [
    {
        "actor_key": "owner",
        "actor_type": "human",
        "display_name": "Owner",
        "group_keys": ["administrator", "finance_manager", "finance_contributor", "report_viewer"],
    }
]

SYSTEM_ACTORS = [
    {
        "actor_key": "system",
        "actor_type": "system",
        "display_name": "System",
        "group_keys": [],
    }
]

SELECTABLE_PERSONAS = [
    {
        "persona_key": "finance_manager",
        "persona_label": "Finance Manager",
        "group_keys": ["finance_manager"],
    },
    {
        "persona_key": "finance_contributor",
        "persona_label": "Finance Contributor",
        "group_keys": ["finance_contributor"],
    },
    {
        "persona_key": "financial_analyst",
        "persona_label": "Financial Analyst",
        "group_keys": ["financial_analyst"],
    },
    {
        "persona_key": "report_viewer",
        "persona_label": "Report Viewer",
        "group_keys": ["report_viewer"],
    },
    {
        "persona_key": "administrator",
        "persona_label": "Administrator",
        "group_keys": ["administrator"],
    },
]

SYSTEM_PERSONAS = [
    {"system_persona_key": "system:importer", "display_name": "System: Importer"},
    {"system_persona_key": "system:validator", "display_name": "System: Validator"},
    {"system_persona_key": "system:report_generator", "display_name": "System: Report Generator"},
    {"system_persona_key": "system:scheduler", "display_name": "System: Scheduler"},
]

DEFAULT_ACTOR_KEY = "owner"


def actors_payload() -> dict[str, Any]:
    return {
        "default_actor_key": DEFAULT_ACTOR_KEY,
        "human_actors": HUMAN_ACTORS,
        "system_actors": SYSTEM_ACTORS,
        "groups": GROUPS,
        "selectable_personas": SELECTABLE_PERSONAS,
        "system_personas": SYSTEM_PERSONAS,
    }


def actor_context_to_json(actor_context: ActorContext) -> str:
    return actor_context.model_dump_json(exclude_none=True)


def actor_context_from_json(value_json: Optional[str]) -> Optional[dict[str, Any]]:
    return json.loads(value_json) if value_json else None


def derive_actor_context(actor: str, actor_context: Optional[ActorContext] = None) -> ActorContext:
    if actor_context is not None:
        return actor_context

    actor_key = actor.strip()
    if actor_key.startswith("system:"):
        return ActorContext(
            actor_key="system",
            actor_type="system",
            display_name="System",
            group_keys=[],
            system_persona_key=actor_key,
            source="compat_actor_string",
        )

    for human_actor in HUMAN_ACTORS:
        if human_actor["actor_key"] == actor_key:
            return ActorContext(
                actor_key=human_actor["actor_key"],
                actor_type="human",
                display_name=human_actor["display_name"],
                persona_key="finance_manager",
                persona_label="Finance Manager",
                group_keys=list(human_actor["group_keys"]),
                source="compat_actor_string",
            )

    if actor_key == "system":
        return ActorContext(
            actor_key="system",
            actor_type="system",
            display_name="System",
            group_keys=[],
            source="compat_actor_string",
        )

    return ActorContext(
        actor_key=actor_key,
        actor_type="human",
        display_name=actor_key,
        group_keys=[],
        source="compat_actor_string",
    )

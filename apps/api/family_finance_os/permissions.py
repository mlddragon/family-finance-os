from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from family_finance_os.actors import ActorContext, derive_actor_context
from family_finance_os.models import PermissionStateEvent

if TYPE_CHECKING:
    from family_finance_os.elevated_mode import ActiveElevatedSession


class ActionKey(str, Enum):
    RUNTIME_STATUS_VIEW = "runtime.status.view"
    RUNTIME_SETTINGS_MANAGE = "runtime.settings.manage"
    USERS_GROUPS_PERSONAS_MANAGE = "users_groups_personas.manage"
    PERMISSIONS_CONFIGURE = "permissions.configure"
    IMPORTS_SETTINGS_CONFIGURE = "imports.settings.configure"
    IMPORTS_RUN = "imports.run"
    TRANSACTIONS_VIEW = "transactions.view"
    TRANSACTIONS_CREATE_MANUAL = "transactions.create_manual"
    TRANSACTIONS_EDIT = "transactions.edit"
    REVIEW_DECIDE = "review.decide"
    REPORTS_VIEW = "reports.view"
    REPORTS_GENERATE = "reports.generate"
    EXPORTS_CREATE = "exports.create"
    MONTHLY_CLOSE_RUN = "monthly_close.run"
    APPROVAL_RULES_CONFIGURE = "approval_rules.configure"
    AUDIT_VIEW = "audit.view"
    SHARING_GRANTS_MANAGE = "sharing_grants.manage"


class DataScopeKey(str, Enum):
    RUNTIME_SETTINGS = "runtime_settings"
    USER_GROUP_PERSONA_ADMIN = "user_group_persona_admin"
    PERMISSION_CONFIGURATION = "permission_configuration"
    SOURCE_PROFILES_IMPORT_CONFIG = "source_profiles_import_config"
    IMPORTED_SOURCE_RECORDS = "imported_source_records"
    CANONICAL_TRANSACTIONS = "canonical_transactions"
    REVIEW_DECISIONS = "review_decisions"
    REPORTS_DASHBOARDS = "reports_dashboards"
    MONTHLY_CLOSE = "monthly_close"
    ADVISOR_EXPORT_ARTIFACTS = "advisor_export_artifacts"
    APPROVAL_RULE_CONFIGURATION = "approval_rule_configuration"
    AUDIT_HISTORY = "audit_history"
    EXTERNAL_SHARING_GRANTS = "external_sharing_grants"
    QA_SYNTHETIC_DATA = "qa_synthetic_data"


class RuleEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    SCOPED = "scoped"
    SUGGEST = "suggest"


class ScopeAccess(str, Enum):
    NONE = "none"
    OWN = "own"
    READ = "read"
    SCOPED = "scoped"
    SUGGEST = "suggest"


GROUP_KEYS = (
    "administrator",
    "finance_manager",
    "finance_contributor",
    "financial_analyst",
    "report_viewer",
)

SYSTEM_PERSONA_GRANTS: dict[str, frozenset[tuple[ActionKey, DataScopeKey]]] = {
    "system:importer": frozenset(
        {
            (ActionKey.IMPORTS_SETTINGS_CONFIGURE, DataScopeKey.SOURCE_PROFILES_IMPORT_CONFIG),
            (ActionKey.IMPORTS_RUN, DataScopeKey.IMPORTED_SOURCE_RECORDS),
        }
    ),
    "system:validator": frozenset(
        {
            (ActionKey.IMPORTS_SETTINGS_CONFIGURE, DataScopeKey.SOURCE_PROFILES_IMPORT_CONFIG),
        }
    ),
    "system:report_generator": frozenset(
        {
            (ActionKey.REPORTS_GENERATE, DataScopeKey.REPORTS_DASHBOARDS),
            (ActionKey.MONTHLY_CLOSE_RUN, DataScopeKey.MONTHLY_CLOSE),
            (ActionKey.EXPORTS_CREATE, DataScopeKey.ADVISOR_EXPORT_ARTIFACTS),
        }
    ),
    "system:monthly_close": frozenset(
        {
            (ActionKey.MONTHLY_CLOSE_RUN, DataScopeKey.MONTHLY_CLOSE),
        }
    ),
    "system:qa_seed": frozenset(
        {
            (ActionKey.IMPORTS_RUN, DataScopeKey.QA_SYNTHETIC_DATA),
            (ActionKey.IMPORTS_SETTINGS_CONFIGURE, DataScopeKey.QA_SYNTHETIC_DATA),
        }
    ),
}

READ_LIKE_ACTIONS = frozenset(
    {
        ActionKey.RUNTIME_STATUS_VIEW,
        ActionKey.TRANSACTIONS_VIEW,
        ActionKey.REPORTS_VIEW,
        ActionKey.AUDIT_VIEW,
    }
)

MUTATING_ACTIONS = frozenset(
    action for action in ActionKey if action not in READ_LIKE_ACTIONS
)

DEFAULT_GROUP_MATRIX: dict[ActionKey, dict[str, RuleEffect]] = {
    ActionKey.RUNTIME_STATUS_VIEW: {
        "administrator": RuleEffect.ALLOW,
        "finance_manager": RuleEffect.ALLOW,
        "finance_contributor": RuleEffect.DENY,
        "financial_analyst": RuleEffect.DENY,
        "report_viewer": RuleEffect.DENY,
    },
    ActionKey.RUNTIME_SETTINGS_MANAGE: {
        "administrator": RuleEffect.ALLOW,
        "finance_manager": RuleEffect.DENY,
        "finance_contributor": RuleEffect.DENY,
        "financial_analyst": RuleEffect.DENY,
        "report_viewer": RuleEffect.DENY,
    },
    ActionKey.USERS_GROUPS_PERSONAS_MANAGE: {
        "administrator": RuleEffect.ALLOW,
        "finance_manager": RuleEffect.DENY,
        "finance_contributor": RuleEffect.DENY,
        "financial_analyst": RuleEffect.DENY,
        "report_viewer": RuleEffect.DENY,
    },
    ActionKey.PERMISSIONS_CONFIGURE: {
        "administrator": RuleEffect.ALLOW,
        "finance_manager": RuleEffect.DENY,
        "finance_contributor": RuleEffect.DENY,
        "financial_analyst": RuleEffect.DENY,
        "report_viewer": RuleEffect.DENY,
    },
    ActionKey.IMPORTS_SETTINGS_CONFIGURE: {
        "administrator": RuleEffect.SCOPED,
        "finance_manager": RuleEffect.ALLOW,
        "finance_contributor": RuleEffect.DENY,
        "financial_analyst": RuleEffect.DENY,
        "report_viewer": RuleEffect.DENY,
    },
    ActionKey.IMPORTS_RUN: {
        "administrator": RuleEffect.DENY,
        "finance_manager": RuleEffect.ALLOW,
        "finance_contributor": RuleEffect.DENY,
        "financial_analyst": RuleEffect.DENY,
        "report_viewer": RuleEffect.DENY,
    },
    ActionKey.TRANSACTIONS_VIEW: {
        "administrator": RuleEffect.SCOPED,
        "finance_manager": RuleEffect.ALLOW,
        "finance_contributor": RuleEffect.SCOPED,
        "financial_analyst": RuleEffect.SCOPED,
        "report_viewer": RuleEffect.DENY,
    },
    ActionKey.TRANSACTIONS_CREATE_MANUAL: {
        "administrator": RuleEffect.DENY,
        "finance_manager": RuleEffect.ALLOW,
        "finance_contributor": RuleEffect.SUGGEST,
        "financial_analyst": RuleEffect.DENY,
        "report_viewer": RuleEffect.DENY,
    },
    ActionKey.TRANSACTIONS_EDIT: {
        "administrator": RuleEffect.DENY,
        "finance_manager": RuleEffect.ALLOW,
        "finance_contributor": RuleEffect.SUGGEST,
        "financial_analyst": RuleEffect.DENY,
        "report_viewer": RuleEffect.DENY,
    },
    ActionKey.REVIEW_DECIDE: {
        "administrator": RuleEffect.DENY,
        "finance_manager": RuleEffect.ALLOW,
        "finance_contributor": RuleEffect.SUGGEST,
        "financial_analyst": RuleEffect.DENY,
        "report_viewer": RuleEffect.DENY,
    },
    ActionKey.REPORTS_VIEW: {
        "administrator": RuleEffect.SCOPED,
        "finance_manager": RuleEffect.ALLOW,
        "finance_contributor": RuleEffect.SCOPED,
        "financial_analyst": RuleEffect.ALLOW,
        "report_viewer": RuleEffect.ALLOW,
    },
    ActionKey.REPORTS_GENERATE: {
        "administrator": RuleEffect.DENY,
        "finance_manager": RuleEffect.ALLOW,
        "finance_contributor": RuleEffect.DENY,
        "financial_analyst": RuleEffect.SCOPED,
        "report_viewer": RuleEffect.DENY,
    },
    ActionKey.EXPORTS_CREATE: {
        "administrator": RuleEffect.DENY,
        "finance_manager": RuleEffect.ALLOW,
        "finance_contributor": RuleEffect.DENY,
        "financial_analyst": RuleEffect.SCOPED,
        "report_viewer": RuleEffect.DENY,
    },
    ActionKey.MONTHLY_CLOSE_RUN: {
        "administrator": RuleEffect.DENY,
        "finance_manager": RuleEffect.ALLOW,
        "finance_contributor": RuleEffect.DENY,
        "financial_analyst": RuleEffect.DENY,
        "report_viewer": RuleEffect.DENY,
    },
    ActionKey.APPROVAL_RULES_CONFIGURE: {
        "administrator": RuleEffect.DENY,
        "finance_manager": RuleEffect.ALLOW,
        "finance_contributor": RuleEffect.DENY,
        "financial_analyst": RuleEffect.DENY,
        "report_viewer": RuleEffect.DENY,
    },
    ActionKey.AUDIT_VIEW: {
        "administrator": RuleEffect.ALLOW,
        "finance_manager": RuleEffect.ALLOW,
        "finance_contributor": RuleEffect.SCOPED,
        "financial_analyst": RuleEffect.SCOPED,
        "report_viewer": RuleEffect.SCOPED,
    },
    ActionKey.SHARING_GRANTS_MANAGE: {
        "administrator": RuleEffect.DENY,
        "finance_manager": RuleEffect.ALLOW,
        "finance_contributor": RuleEffect.DENY,
        "financial_analyst": RuleEffect.DENY,
        "report_viewer": RuleEffect.DENY,
    },
}

DEFAULT_DATA_SCOPE_MATRIX: dict[DataScopeKey, dict[str, ScopeAccess]] = {
    DataScopeKey.RUNTIME_SETTINGS: {
        "administrator": ScopeAccess.OWN,
        "finance_manager": ScopeAccess.READ,
        "finance_contributor": ScopeAccess.NONE,
        "financial_analyst": ScopeAccess.NONE,
        "report_viewer": ScopeAccess.NONE,
    },
    DataScopeKey.USER_GROUP_PERSONA_ADMIN: {
        "administrator": ScopeAccess.OWN,
        "finance_manager": ScopeAccess.NONE,
        "finance_contributor": ScopeAccess.NONE,
        "financial_analyst": ScopeAccess.NONE,
        "report_viewer": ScopeAccess.NONE,
    },
    DataScopeKey.PERMISSION_CONFIGURATION: {
        "administrator": ScopeAccess.OWN,
        "finance_manager": ScopeAccess.NONE,
        "finance_contributor": ScopeAccess.NONE,
        "financial_analyst": ScopeAccess.NONE,
        "report_viewer": ScopeAccess.NONE,
    },
    DataScopeKey.SOURCE_PROFILES_IMPORT_CONFIG: {
        "administrator": ScopeAccess.SCOPED,
        "finance_manager": ScopeAccess.OWN,
        "finance_contributor": ScopeAccess.NONE,
        "financial_analyst": ScopeAccess.NONE,
        "report_viewer": ScopeAccess.NONE,
    },
    DataScopeKey.IMPORTED_SOURCE_RECORDS: {
        "administrator": ScopeAccess.SCOPED,
        "finance_manager": ScopeAccess.OWN,
        "finance_contributor": ScopeAccess.NONE,
        "financial_analyst": ScopeAccess.SCOPED,
        "report_viewer": ScopeAccess.NONE,
    },
    DataScopeKey.CANONICAL_TRANSACTIONS: {
        "administrator": ScopeAccess.SCOPED,
        "finance_manager": ScopeAccess.OWN,
        "finance_contributor": ScopeAccess.SCOPED,
        "financial_analyst": ScopeAccess.SCOPED,
        "report_viewer": ScopeAccess.NONE,
    },
    DataScopeKey.REVIEW_DECISIONS: {
        "administrator": ScopeAccess.SCOPED,
        "finance_manager": ScopeAccess.OWN,
        "finance_contributor": ScopeAccess.SUGGEST,
        "financial_analyst": ScopeAccess.SCOPED,
        "report_viewer": ScopeAccess.NONE,
    },
    DataScopeKey.REPORTS_DASHBOARDS: {
        "administrator": ScopeAccess.SCOPED,
        "finance_manager": ScopeAccess.OWN,
        "finance_contributor": ScopeAccess.SCOPED,
        "financial_analyst": ScopeAccess.SCOPED,
        "report_viewer": ScopeAccess.READ,
    },
    DataScopeKey.MONTHLY_CLOSE: {
        "administrator": ScopeAccess.NONE,
        "finance_manager": ScopeAccess.OWN,
        "finance_contributor": ScopeAccess.NONE,
        "financial_analyst": ScopeAccess.SCOPED,
        "report_viewer": ScopeAccess.READ,
    },
    DataScopeKey.ADVISOR_EXPORT_ARTIFACTS: {
        "administrator": ScopeAccess.NONE,
        "finance_manager": ScopeAccess.OWN,
        "finance_contributor": ScopeAccess.NONE,
        "financial_analyst": ScopeAccess.SCOPED,
        "report_viewer": ScopeAccess.READ,
    },
    DataScopeKey.APPROVAL_RULE_CONFIGURATION: {
        "administrator": ScopeAccess.NONE,
        "finance_manager": ScopeAccess.OWN,
        "finance_contributor": ScopeAccess.NONE,
        "financial_analyst": ScopeAccess.NONE,
        "report_viewer": ScopeAccess.NONE,
    },
    DataScopeKey.AUDIT_HISTORY: {
        "administrator": ScopeAccess.READ,
        "finance_manager": ScopeAccess.READ,
        "finance_contributor": ScopeAccess.SCOPED,
        "financial_analyst": ScopeAccess.SCOPED,
        "report_viewer": ScopeAccess.SCOPED,
    },
    DataScopeKey.EXTERNAL_SHARING_GRANTS: {
        "administrator": ScopeAccess.NONE,
        "finance_manager": ScopeAccess.OWN,
        "finance_contributor": ScopeAccess.NONE,
        "financial_analyst": ScopeAccess.NONE,
        "report_viewer": ScopeAccess.NONE,
    },
    DataScopeKey.QA_SYNTHETIC_DATA: {
        "administrator": ScopeAccess.SCOPED,
        "finance_manager": ScopeAccess.SCOPED,
        "finance_contributor": ScopeAccess.SCOPED,
        "financial_analyst": ScopeAccess.SCOPED,
        "report_viewer": ScopeAccess.SCOPED,
    },
}


@dataclass(frozen=True)
class PermissionEvaluation:
    allowed: bool
    suggestion_allowed: bool
    action_key: str
    data_scope_key: str
    action_effect: Optional[str] = None
    scope_access: Optional[str] = None
    denied_reason: Optional[str] = None


class PermissionDeniedError(Exception):
    def __init__(
        self,
        action_key: str,
        data_scope_key: str,
        *,
        suggestion_allowed: bool = False,
    ):
        self.code = "permission_denied"
        self.message = (
            f"Action {action_key} on data scope {data_scope_key} is not allowed "
            "for the current actor context."
        )
        self.status_code = 403
        self.action_key = action_key
        self.data_scope_key = data_scope_key
        self.suggestion_allowed = suggestion_allowed
        super().__init__(self.message)


class PermissionPreviewRequest(BaseModel):
    persona_key: str = Field(min_length=1)
    action_key: str = Field(min_length=1)
    data_scope_key: str = Field(min_length=1)
    scope_selector: Optional[str] = None


def action_is_mutating(action_key: ActionKey) -> bool:
    return action_key in MUTATING_ACTIONS


def _resolve_action_effects(effects: list[RuleEffect], action_key: ActionKey) -> tuple[bool, bool, Optional[RuleEffect]]:
    if not effects:
        return False, False, None

    has_allow = RuleEffect.ALLOW in effects
    has_scoped_read = RuleEffect.SCOPED in effects and action_key in READ_LIKE_ACTIONS
    has_suggest = RuleEffect.SUGGEST in effects

    if has_allow or has_scoped_read:
        return True, False, RuleEffect.ALLOW if has_allow else RuleEffect.SCOPED

    if has_suggest:
        return False, True, RuleEffect.SUGGEST

    if RuleEffect.DENY in effects:
        return False, False, RuleEffect.DENY

    if RuleEffect.SCOPED in effects:
        return False, False, RuleEffect.SCOPED

    return False, False, None


def _resolve_scope_access(access_levels: list[ScopeAccess], *, is_mutation: bool) -> tuple[bool, bool, Optional[ScopeAccess]]:
    if not access_levels:
        return False, False, None

    if any(level == ScopeAccess.OWN for level in access_levels):
        return True, False, ScopeAccess.OWN

    if is_mutation:
        if any(level == ScopeAccess.SUGGEST for level in access_levels):
            return False, True, ScopeAccess.SUGGEST
        return False, False, ScopeAccess.NONE

    if any(level in {ScopeAccess.READ, ScopeAccess.SCOPED, ScopeAccess.SUGGEST} for level in access_levels):
        return True, False, ScopeAccess.READ

    if all(level == ScopeAccess.NONE for level in access_levels):
        return False, False, ScopeAccess.NONE

    return False, False, access_levels[0]


def _parse_action_key(value: str) -> Optional[ActionKey]:
    try:
        return ActionKey(value)
    except ValueError:
        return None


def _parse_data_scope_key(value: str) -> Optional[DataScopeKey]:
    try:
        return DataScopeKey(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class _OverrideRule:
    target_kind: str
    target_id: str
    action_key: ActionKey
    data_scope_key: DataScopeKey
    effect: RuleEffect
    scope_selector: Optional[str]
    active: bool


def _evaluation_group_keys(actor_context: ActorContext) -> list[str]:
    if actor_context.source == "local_selector" and actor_context.persona_key:
        from family_finance_os.actors import SELECTABLE_PERSONAS

        for persona in SELECTABLE_PERSONAS:
            if persona["persona_key"] == actor_context.persona_key:
                return list(persona["group_keys"])

    if actor_context.group_keys:
        return list(actor_context.group_keys)

    if actor_context.actor_type == "human" and actor_context.source == "compat_actor_string":
        from family_finance_os.actors import DEFAULT_ACTOR_KEY, HUMAN_ACTORS

        for human_actor in HUMAN_ACTORS:
            if human_actor["actor_key"] == actor_context.actor_key:
                return list(human_actor["group_keys"])
        for human_actor in HUMAN_ACTORS:
            if human_actor["actor_key"] == DEFAULT_ACTOR_KEY:
                return list(human_actor["group_keys"])
        return ["finance_manager"]

    return []


def _effective_group_keys(actor_context: ActorContext) -> list[str]:
    return _evaluation_group_keys(actor_context)


class PermissionEvaluator:
    def __init__(self, session: Optional[Session] = None) -> None:
        self._session = session
        self._override_rules: Optional[list[_OverrideRule]] = None

    def _load_override_rules(self) -> list[_OverrideRule]:
        if self._override_rules is not None:
            return self._override_rules

        if self._session is None:
            self._override_rules = []
            return self._override_rules

        events = self._session.scalars(
            select(PermissionStateEvent).order_by(
                PermissionStateEvent.created_at,
                PermissionStateEvent.id,
            )
        ).all()

        inactive_ids: set[str] = set()
        for event in events:
            if event.supersedes_event_id:
                inactive_ids.add(event.supersedes_event_id)
            if event.operation == "revoke_rule" and event.supersedes_event_id:
                inactive_ids.add(event.supersedes_event_id)

        rules: list[_OverrideRule] = []
        for event in events:
            if event.id in inactive_ids:
                continue
            action_key = _parse_action_key(event.action_key)
            data_scope_key = _parse_data_scope_key(event.data_scope_key)
            if action_key is None or data_scope_key is None:
                continue
            if event.operation == "revoke_rule":
                continue
            effect = RuleEffect.ALLOW if event.effect == "allow" else RuleEffect.DENY
            rules.append(
                _OverrideRule(
                    target_kind=event.target_kind,
                    target_id=event.target_id,
                    action_key=action_key,
                    data_scope_key=data_scope_key,
                    effect=effect,
                    scope_selector=event.scope_selector,
                    active=True,
                )
            )

        self._override_rules = rules
        return self._override_rules

    def _override_effects(
        self,
        actor_context: ActorContext,
        action_key: ActionKey,
        data_scope_key: DataScopeKey,
        scope_selector: Optional[str],
    ) -> list[RuleEffect]:
        effects: list[RuleEffect] = []
        group_keys = set(_effective_group_keys(actor_context))
        persona_key = actor_context.persona_key
        system_persona_key = actor_context.system_persona_key

        for rule in self._load_override_rules():
            if rule.action_key != action_key or rule.data_scope_key != data_scope_key:
                continue
            if rule.scope_selector and rule.scope_selector != scope_selector:
                continue
            matched = False
            if rule.target_kind == "group" and rule.target_id in group_keys:
                matched = True
            elif rule.target_kind == "persona" and persona_key == rule.target_id:
                matched = True
            elif rule.target_kind == "system_persona" and system_persona_key == rule.target_id:
                matched = True
            if matched:
                effects.append(rule.effect)
        return effects

    def _default_action_effects(self, actor_context: ActorContext, action_key: ActionKey) -> list[RuleEffect]:
        row = DEFAULT_GROUP_MATRIX.get(action_key, {})
        effects: list[RuleEffect] = []
        for group_key in _effective_group_keys(actor_context):
            effect = row.get(group_key, RuleEffect.DENY)
            effects.append(effect)
        return effects

    def _default_scope_access(self, actor_context: ActorContext, data_scope_key: DataScopeKey) -> list[ScopeAccess]:
        row = DEFAULT_DATA_SCOPE_MATRIX.get(data_scope_key, {})
        access_levels: list[ScopeAccess] = []
        for group_key in _effective_group_keys(actor_context):
            access_levels.append(row.get(group_key, ScopeAccess.NONE))
        return access_levels

    def evaluate(
        self,
        actor_context: ActorContext,
        action_key: str,
        data_scope_key: str,
        *,
        scope_selector: Optional[str] = None,
        elevated_session: Optional[Any] = None,
    ) -> PermissionEvaluation:
        parsed_action = _parse_action_key(action_key)
        parsed_scope = _parse_data_scope_key(data_scope_key)
        if parsed_action is None or parsed_scope is None:
            return PermissionEvaluation(
                allowed=False,
                suggestion_allowed=False,
                action_key=action_key,
                data_scope_key=data_scope_key,
                denied_reason="unknown_action_or_scope",
            )

        system_persona_key = actor_context.system_persona_key
        if system_persona_key:
            grants = SYSTEM_PERSONA_GRANTS.get(system_persona_key, frozenset())
            if (parsed_action, parsed_scope) in grants:
                return PermissionEvaluation(
                    allowed=True,
                    suggestion_allowed=False,
                    action_key=action_key,
                    data_scope_key=data_scope_key,
                    action_effect=RuleEffect.ALLOW.value,
                    scope_access=ScopeAccess.OWN.value,
                )

        override_effects = self._override_effects(
            actor_context,
            parsed_action,
            parsed_scope,
            scope_selector,
        )
        if RuleEffect.DENY in override_effects:
            return PermissionEvaluation(
                allowed=False,
                suggestion_allowed=False,
                action_key=action_key,
                data_scope_key=data_scope_key,
                action_effect=RuleEffect.DENY.value,
                denied_reason="explicit_deny_override",
            )

        default_effects = self._default_action_effects(actor_context, parsed_action)
        combined_effects = default_effects + [
            effect for effect in override_effects if effect == RuleEffect.ALLOW
        ]
        action_allowed, suggestion_from_action, action_effect = _resolve_action_effects(
            combined_effects,
            parsed_action,
        )

        is_mutation = action_is_mutating(parsed_action)
        default_scope = self._default_scope_access(actor_context, parsed_scope)
        scope_allowed, suggestion_from_scope, scope_access = _resolve_scope_access(
            default_scope,
            is_mutation=is_mutation,
        )

        suggestion_allowed = suggestion_from_action or suggestion_from_scope
        allowed = action_allowed and scope_allowed

        denied_reason: Optional[str] = None
        if not allowed:
            if not action_allowed:
                denied_reason = "action_not_allowed"
            elif not scope_allowed:
                denied_reason = "data_scope_not_allowed"

        evaluation = PermissionEvaluation(
            allowed=allowed,
            suggestion_allowed=suggestion_allowed and not allowed,
            action_key=action_key,
            data_scope_key=data_scope_key,
            action_effect=action_effect.value if action_effect else None,
            scope_access=scope_access.value if scope_access else None,
            denied_reason=denied_reason,
        )

        if elevated_session is not None and parsed_action is not None:
            from family_finance_os.elevated_mode import apply_elevated_mode_restriction

            return apply_elevated_mode_restriction(evaluation, parsed_action, elevated_session)

        return evaluation

    def require(
        self,
        actor: str,
        action_key: ActionKey | str,
        data_scope_key: DataScopeKey | str,
        *,
        actor_context: Optional[ActorContext] = None,
        scope_selector: Optional[str] = None,
        elevated_session: Optional[Any] = None,
    ) -> PermissionEvaluation:
        resolved_context = derive_actor_context(actor, actor_context)
        action_value = action_key.value if isinstance(action_key, ActionKey) else action_key
        scope_value = data_scope_key.value if isinstance(data_scope_key, DataScopeKey) else data_scope_key
        evaluation = self.evaluate(
            resolved_context,
            action_value,
            scope_value,
            scope_selector=scope_selector,
            elevated_session=elevated_session,
        )
        if not evaluation.allowed:
            raise PermissionDeniedError(
                action_value,
                scope_value,
                suggestion_allowed=evaluation.suggestion_allowed,
            )
        return evaluation


def actor_context_for_persona(persona_key: str) -> ActorContext:
    from family_finance_os.actors import SELECTABLE_PERSONAS

    for persona in SELECTABLE_PERSONAS:
        if persona["persona_key"] == persona_key:
            return ActorContext(
                actor_key=f"preview:{persona_key}",
                actor_type="human",
                display_name=persona["persona_label"],
                persona_key=persona_key,
                persona_label=persona["persona_label"],
                group_keys=list(persona["group_keys"]),
                source="local_selector",
            )
    raise ValueError(f"Unknown persona_key: {persona_key}")


def effective_permission_payload(evaluation: PermissionEvaluation) -> dict[str, Any]:
    return {
        "allowed": evaluation.allowed,
        "suggestion_allowed": evaluation.suggestion_allowed,
        "action_key": evaluation.action_key,
        "data_scope_key": evaluation.data_scope_key,
        "action_effect": evaluation.action_effect,
        "scope_access": evaluation.scope_access,
        "denied_reason": evaluation.denied_reason,
    }

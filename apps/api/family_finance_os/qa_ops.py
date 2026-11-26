"""QA-only data operations shared by the CLI scripts and the QA Options API.

Everything here mutates the QA synthetic data root and must stay behind the
``qa_controls_enabled`` runtime gate plus a ``qa_synthetic_data`` permission check.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from sqlalchemy.orm import Session, sessionmaker

from family_finance_os.actors import ActorContext
from family_finance_os.category_service import seed_default_categories
from family_finance_os.database import create_sqlite_engine, resolve_database_path, upgrade_database
from family_finance_os.decision_events import DecisionEventRequest
from family_finance_os.import_validation import (
    ImportValidationError,
    accept_import_batch,
    list_validation_findings,
    refresh_source_coverage_findings,
    save_upload,
    validate_import_batch,
)
from family_finance_os.ledger_normalization import list_transactions
from family_finance_os.operator_summary import operator_summary_payload
from family_finance_os.qa_assets import (
    QaAssetError,
    materialize_vendor_synthetic_fixtures,
    read_import_pack_asset,
)
from family_finance_os.reporting import (
    AdvisorExportRequest,
    MonthlyCloseRequest,
    ReportingError,
    ReportRunRequest,
    create_advisor_export,
    create_monthly_close,
    list_artifacts,
    run_reports,
)
from family_finance_os.runtime import (
    REQUIRED_DATA_ROOT_DIRS,
    RuntimeEnvironment,
    SYNTHETIC_ARTIFACT_MARKER,
    bootstrap_data_root,
    runtime_environment_from_env,
    validate_data_root,
)
from family_finance_os.settings_service import (
    SettingChange,
    SettingsPatchRequest,
    apply_settings_patch,
    seed_default_settings,
)
from family_finance_os.source_profiles import list_source_profiles
from family_finance_os.status import status_payload
from family_finance_os.suggestions import route_review_decide


SCENARIO_VERSION = "0.4.0"
RESET_CONFIRMATION = "RESET QA DATA"
BASELINE_SCENARIO = "baseline"
STALE_SOURCE_SCENARIO = "stale-source"
BLOCKED_IMPORT_SCENARIO = "blocked-import"
REVIEW_BACKLOG_SCENARIO = "review-backlog"
MONTHLY_CLOSE_READY_SCENARIO = "monthly-close-ready"

SOURCE_KEYS = (
    "alliant_checking",
    "alliant_savings",
    "alliant_credit_card",
    "chase_prime_visa",
)


class QaOpsError(RuntimeError):
    """Raised when a QA operation is refused or fails."""

    def __init__(self, message: str, *, code: str = "qa_operation_failed", status_code: int = 409):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


# Preserved for the CLI wrappers and existing callers that catch these names.
QaSeedError = QaOpsError
QaResetError = QaOpsError


@dataclass
class SeedContext:
    session: Session
    data_root: Path
    runtime_environment: RuntimeEnvironment


@dataclass(frozen=True)
class QaScenario:
    key: str
    display_name: str
    description: str
    when_to_use: str
    changes_from_default: tuple[str, ...]
    seed: Callable[[SeedContext], dict[str, Any]]

    def catalog_entry(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "display_name": self.display_name,
            "description": self.description,
            "when_to_use": self.when_to_use,
            "changes_from_default": list(self.changes_from_default),
        }


def _system_actor_context(system_persona_key: str) -> ActorContext:
    return ActorContext(
        actor_key="system",
        actor_type="system",
        display_name="System",
        group_keys=[],
        system_persona_key=system_persona_key,
        source="system",
    )


def _owner_actor_context() -> ActorContext:
    return ActorContext(
        actor_key="owner",
        actor_type="human",
        display_name="Owner",
        persona_key="finance_manager",
        persona_label="Finance Manager",
        group_keys=["administrator", "finance_manager"],
        source="local_selector",
    )


def _source_files(*, stale_sources: frozenset[str] = frozenset()) -> dict[str, str]:
    chase_file = (
        "chase_prime_visa_stale.csv" if "chase_prime_visa" in stale_sources else "chase_prime_visa.csv"
    )
    return {
        "alliant_checking": read_import_pack_asset("alliant_checking.csv"),
        "alliant_savings": read_import_pack_asset("alliant_savings.csv"),
        "alliant_credit_card": read_import_pack_asset("alliant_credit_card.csv"),
        "chase_prime_visa": read_import_pack_asset(chase_file),
    }


def _apply_settings(context: SeedContext, actor_context: ActorContext, changes: list[SettingChange]) -> None:
    apply_settings_patch(
        context.session,
        SettingsPatchRequest(actor="system", actor_context=actor_context, changes=changes),
    )
    refresh_source_coverage_findings(context.session)
    context.session.commit()


def _confirm_source_profiles(context: SeedContext) -> None:
    _apply_settings(
        context,
        _system_actor_context("system:importer"),
        [
            SettingChange(
                domain="sources",
                setting_key=f"sources.{profile.source_key}.profile_confirmation_status",
                value="owner_confirmed_header_sample",
                note=f"Synthetic QA confirms header-only source profile for {profile.source_key}.",
            )
            for profile in list_source_profiles()
        ],
    )


def _enable_required_sources(context: SeedContext, source_keys: tuple[str, ...] = SOURCE_KEYS) -> None:
    _apply_settings(
        context,
        _system_actor_context("system:validator"),
        [
            SettingChange(
                domain="sources",
                setting_key=f"sources.{source_key}.required",
                value=True,
                note=f"Synthetic QA marks {source_key} as required for scenario coverage.",
            )
            for source_key in source_keys
        ],
    )


def _upload_source(context: SeedContext, source_key: Optional[str], content: str, *, scenario_key: str) -> str:
    filename_source = source_key or "unknown_source"
    filename = f"SYNTHETIC_{filename_source}_{scenario_key}.csv"
    try:
        batch = save_upload(
            context.session,
            context.data_root,
            filename,
            content.encode("utf-8"),
            source_key_hint=source_key,
        )
    except ImportValidationError as exc:
        raise QaOpsError(f"upload {filename_source} failed: {exc.message}", code=exc.code) from exc
    context.session.commit()
    return batch.id


def _accepted_imports(context: SeedContext, *, scenario_key: str, source_files: dict[str, str]) -> list[str]:
    accepted_batch_ids: list[str] = []
    for source_key, content in source_files.items():
        batch_id = _upload_source(context, source_key, content, scenario_key=scenario_key)
        validate_import_batch(context.session, batch_id)
        try:
            accept_import_batch(context.session, context.data_root, batch_id, acknowledge_warnings=True)
        except ImportValidationError as exc:
            raise QaOpsError(f"accept {source_key} failed: {exc.message}", code=exc.code) from exc
        accepted_batch_ids.append(batch_id)
    return accepted_batch_ids


def _review_transactions(context: SeedContext, *, limit: Optional[int] = None) -> int:
    transactions = list_transactions(context.session)
    selected = transactions if limit is None else transactions[:limit]
    for transaction in selected:
        route_review_decide(
            context.session,
            DecisionEventRequest(
                target_type="canonical_transaction",
                target_id=transaction["id"],
                decision_type="review_status_change",
                field_name="review_status",
                proposed_value="reviewed",
                approved_value="reviewed",
                actor="owner",
                actor_context=_owner_actor_context(),
                suggestion_source="owner",
                explicit_user_action=True,
                notes="Synthetic QA review decision.",
            ),
        )
    return len(selected)


def _run_reports(context: SeedContext) -> dict[str, Any]:
    return run_reports(
        context.session,
        context.data_root,
        ReportRunRequest(actor="system", actor_context=_system_actor_context("system:report_generator")),
        synthetic_artifact_marker=context.runtime_environment.synthetic_artifact_marker,
    )


def _monthly_close(context: SeedContext, *, status: str, notes: str) -> dict[str, Any]:
    actor_context = (
        _owner_actor_context() if status == "final" else _system_actor_context("system:report_generator")
    )
    return create_monthly_close(
        context.session,
        context.data_root,
        MonthlyCloseRequest(
            actor="owner" if status == "final" else "system",
            actor_context=actor_context,
            notes=notes,
        ),
        status=status,
        synthetic_artifact_marker=context.runtime_environment.synthetic_artifact_marker,
    )


def _advisor_export(context: SeedContext) -> dict[str, Any]:
    return create_advisor_export(
        context.session,
        context.data_root,
        AdvisorExportRequest(actor="system", actor_context=_system_actor_context("system:report_generator")),
        synthetic_artifact_marker=context.runtime_environment.synthetic_artifact_marker,
    )


def _seed_baseline(context: SeedContext) -> dict[str, Any]:
    _confirm_source_profiles(context)
    accepted_batch_ids = _accepted_imports(
        context, scenario_key=BASELINE_SCENARIO, source_files=_source_files()
    )
    reviewed_count = _review_transactions(context, limit=4)
    reports = _run_reports(context)
    draft_close = _monthly_close(context, status="draft", notes="Synthetic baseline draft close.")
    advisor_export = _advisor_export(context)

    return {
        "description": (
            "Accepted imports from the synthetic import pack with several reviewed transactions, "
            "reports, draft close, and advisor export."
        ),
        "accepted_import_batch_ids": accepted_batch_ids,
        "accepted_source_keys": sorted(_source_files().keys()),
        "reviewed_transaction_count": reviewed_count,
        "artifact_counts": {
            "reports": len(reports["artifacts"]),
            "monthly_close": len(draft_close["artifacts"]),
            "advisor_export": len(advisor_export["artifacts"]),
        },
        "expected_operator_state": {
            "next_action": "review_ledger_decisions",
            "open_blocking": 0,
            "review_unreviewed_min": 1,
        },
    }


def _seed_stale_source(context: SeedContext) -> dict[str, Any]:
    _confirm_source_profiles(context)
    _enable_required_sources(context)
    accepted_batch_ids = _accepted_imports(
        context,
        scenario_key=STALE_SOURCE_SCENARIO,
        source_files=_source_files(stale_sources=frozenset({"chase_prime_visa"})),
    )
    reviewed_count = _review_transactions(context)
    try:
        _monthly_close(context, status="final", notes="Synthetic stale-source final close should be blocked.")
    except ReportingError as exc:
        blocked_finalize_status_code = exc.status_code
    else:
        blocked_finalize_status_code = 200

    return {
        "description": "Required source coverage where Chase is accepted but stale against the freshness threshold.",
        "accepted_import_batch_ids": accepted_batch_ids,
        "accepted_source_keys": sorted(_source_files().keys()),
        "reviewed_transaction_count": reviewed_count,
        "blocked_finalize_status_code": blocked_finalize_status_code,
        "expected_operator_state": {
            "next_action": "run_reports_monthly_close",
            "stale_required_sources": ["chase_prime_visa"],
            "open_warning_codes": ["source_stale"],
            "final_close_blocked": True,
        },
    }


def _seed_blocked_import(context: SeedContext) -> dict[str, Any]:
    _confirm_source_profiles(context)
    batch_id = _upload_source(
        context,
        None,
        read_import_pack_asset("blocked_wrong_header.csv"),
        scenario_key=BLOCKED_IMPORT_SCENARIO,
    )
    validation = validate_import_batch(context.session, batch_id)
    try:
        accept_import_batch(context.session, context.data_root, batch_id, acknowledge_warnings=True)
    except ImportValidationError as exc:
        blocked_accept_status_code = exc.status_code
    else:
        blocked_accept_status_code = 200

    return {
        "description": "A blocked schema mismatch import that should remain unresolved and quarantined.",
        "blocked_import_batch_id": batch_id,
        "blocked_accept_status_code": blocked_accept_status_code,
        "blocked_validation_codes": sorted({finding["code"] for finding in validation["findings"]}),
        "expected_operator_state": {
            "next_action": "resolve_validation_blockers",
            "open_blocking_codes": ["schema_mismatch"],
            "quarantine_expected": True,
        },
    }


def _seed_review_backlog(context: SeedContext) -> dict[str, Any]:
    _confirm_source_profiles(context)
    accepted_batch_ids = _accepted_imports(
        context, scenario_key=REVIEW_BACKLOG_SCENARIO, source_files=_source_files()
    )
    return {
        "description": "Accepted imports with intentionally unreviewed transactions for Ledger Review QA.",
        "accepted_import_batch_ids": accepted_batch_ids,
        "accepted_source_keys": sorted(_source_files().keys()),
        "expected_operator_state": {
            "next_action": "review_ledger_decisions",
            "review_unreviewed_min": 1,
            "open_blocking": 0,
        },
    }


def _seed_monthly_close_ready(context: SeedContext) -> dict[str, Any]:
    _confirm_source_profiles(context)
    _enable_required_sources(context)
    accepted_batch_ids = _accepted_imports(
        context, scenario_key=MONTHLY_CLOSE_READY_SCENARIO, source_files=_source_files()
    )
    reviewed_count = _review_transactions(context)
    reports = _run_reports(context)
    draft_close = _monthly_close(context, status="draft", notes="Synthetic monthly-close-ready draft close.")
    final_close = _monthly_close(context, status="final", notes="Synthetic monthly-close-ready final close.")
    advisor_export = _advisor_export(context)
    return {
        "description": (
            "Fully reviewed and final-close-ready dataset with reports, draft close, final close, "
            "and advisor export."
        ),
        "accepted_import_batch_ids": accepted_batch_ids,
        "accepted_source_keys": sorted(_source_files().keys()),
        "reviewed_transaction_count": reviewed_count,
        "monthly_close_status": final_close["monthly_close"]["status"],
        "artifact_counts": {
            "reports": len(reports["artifacts"]),
            "monthly_close_draft": len(draft_close["artifacts"]),
            "monthly_close_final": len(final_close["artifacts"]),
            "advisor_export": len(advisor_export["artifacts"]),
        },
        "expected_operator_state": {
            "next_action": "refresh_source_data",
            "monthly_close_status": "final",
            "ready_for_final": True,
            "open_blocking": 0,
            "review_unreviewed": 0,
        },
    }


SCENARIO_CATALOG: tuple[QaScenario, ...] = (
    QaScenario(
        key=BASELINE_SCENARIO,
        display_name="Baseline closed loop",
        description=(
            "Imports the four synthetic sources, reviews a handful of transactions, then runs reports, "
            "a draft monthly close, and an advisor export."
        ),
        when_to_use="Default demo and smoke testing. Start here when you just need a working dataset.",
        changes_from_default=(
            "Accepts 4 source imports (Alliant checking, savings, credit card, Chase Prime Visa).",
            "Marks the first 4 transactions reviewed; the rest stay unreviewed.",
            "Generates report, draft monthly close, and advisor export artifacts.",
            "Confirms header-only source profiles so imports are not blocked.",
        ),
        seed=_seed_baseline,
    ),
    QaScenario(
        key=STALE_SOURCE_SCENARIO,
        display_name="Stale source warning",
        description=(
            "Same four sources, but Chase Prime Visa is imported from a stale file so freshness warnings "
            "fire and the final monthly close is refused."
        ),
        when_to_use="Testing stale-source warnings, required-source coverage, and finalize blockers.",
        changes_from_default=(
            "Uses the stale chase_prime_visa_stale.csv instead of the fresh file.",
            "Marks all four sources required, which turns staleness into a close blocker.",
            "Reviews every transaction so staleness is the only remaining blocker.",
            "Attempts a final close and records the refusal.",
        ),
        seed=_seed_stale_source,
    ),
    QaScenario(
        key=BLOCKED_IMPORT_SCENARIO,
        display_name="Blocked import",
        description=(
            "Uploads a CSV with the wrong header so validation blocks it and the file lands in quarantine."
        ),
        when_to_use="Testing validation, quarantine, and blocker-resolution UX.",
        changes_from_default=(
            "Imports only blocked_wrong_header.csv; no transactions are created.",
            "Leaves one open blocking schema_mismatch validation finding.",
            "Moves the rejected file into DATA_ROOT/quarantine.",
        ),
        seed=_seed_blocked_import,
    ),
    QaScenario(
        key=REVIEW_BACKLOG_SCENARIO,
        display_name="Review backlog",
        description="Accepts all four source imports and leaves every transaction unreviewed.",
        when_to_use="Testing the ledger review queue, bulk review flows, and review-driven next actions.",
        changes_from_default=(
            "Accepts 4 source imports with no review decisions recorded.",
            "Leaves the full transaction set unreviewed.",
            "Generates no report, close, or export artifacts.",
        ),
        seed=_seed_review_backlog,
    ),
    QaScenario(
        key=MONTHLY_CLOSE_READY_SCENARIO,
        display_name="Monthly close ready",
        description=(
            "Fully reviewed dataset with reports, a draft close, a final close, and an advisor export "
            "already produced."
        ),
        when_to_use="Testing the finalized close state, advisor exports, and post-close read-only behavior.",
        changes_from_default=(
            "Accepts 4 source imports and marks all four sources required.",
            "Reviews every transaction.",
            "Runs reports, then both a draft and a final monthly close.",
            "Produces an advisor export artifact.",
        ),
        seed=_seed_monthly_close_ready,
    ),
)

SCENARIOS: dict[str, QaScenario] = {scenario.key: scenario for scenario in SCENARIO_CATALOG}


def scenario_catalog_payload() -> dict[str, Any]:
    return {
        "scenario_version": SCENARIO_VERSION,
        "reset_confirmation_phrase": RESET_CONFIRMATION,
        "scenarios": [scenario.catalog_entry() for scenario in SCENARIO_CATALOG],
    }


def require_qa_runtime(runtime_environment: RuntimeEnvironment) -> None:
    if not runtime_environment.qa_controls_enabled:
        raise QaOpsError(
            "QA data operations require APP_ENV=qa, DATASET_KIND=synthetic, and DEV_MODE=true.",
            code="qa_controls_disabled",
            status_code=403,
        )


def personal_default_data_root() -> Path:
    return (Path.home() / "FamilyFinanceOS_Data").expanduser().resolve()


def reset_qa_data_root(
    *,
    data_root: Path,
    app_env: str,
    dataset_kind: str,
    confirmation: str,
    repo_root: Optional[Path] = None,
) -> Path:
    if confirmation != RESET_CONFIRMATION:
        raise QaOpsError(
            f'QA reset requires exact confirmation: "{RESET_CONFIRMATION}".',
            code="qa_reset_confirmation_invalid",
            status_code=422,
        )
    if app_env != "qa" or dataset_kind != "synthetic":
        raise QaOpsError(
            "QA reset is allowed only for QA/synthetic environment identity.",
            code="qa_controls_disabled",
            status_code=403,
        )

    resolved_data_root = validate_data_root(data_root, repo_root=repo_root)
    if resolved_data_root == personal_default_data_root():
        raise QaOpsError(
            "QA reset refuses the personal default data root.",
            code="qa_reset_personal_data_root",
            status_code=403,
        )

    if resolved_data_root.exists():
        shutil.rmtree(resolved_data_root)
    resolved_data_root.mkdir(parents=True, exist_ok=True)
    for directory_name in REQUIRED_DATA_ROOT_DIRS:
        (resolved_data_root / directory_name).mkdir(exist_ok=True)
    materialize_vendor_synthetic_fixtures(resolved_data_root)
    return resolved_data_root


def _default_session_factory(data_root: Path) -> Callable[[], Session]:
    database_path = resolve_database_path(data_root / "database")
    upgrade_database(database_path)
    engine = create_sqlite_engine(database_path)
    factory = sessionmaker(bind=engine)

    def create_session() -> Session:
        return factory()

    return create_session


def _operator_state(session: Session, *, runtime: dict[str, Any]) -> dict[str, Any]:
    refresh_source_coverage_findings(session)
    session.commit()
    findings = list_validation_findings(session)
    transactions = list_transactions(session)
    open_findings = [finding for finding in findings if finding["status"] == "open"]
    return {
        "operator_summary": operator_summary_payload(session, runtime=runtime),
        "validation_findings": {
            "total": len(findings),
            "open_blocking": len([f for f in open_findings if f["severity"] == "blocking"]),
            "open_warning": len([f for f in open_findings if f["severity"] == "warning"]),
            "codes": sorted({finding["code"] for finding in open_findings}),
        },
        "transactions": {
            "total": len(transactions),
            "reviewed": len([t for t in transactions if t["review_status"] == "reviewed"]),
            "unreviewed": len([t for t in transactions if t["review_status"] == "unreviewed"]),
            "blocked": len([t for t in transactions if t["validation_status"] == "blocked"]),
        },
        "artifact_total": len(list_artifacts(session)),
    }


def _write_manifest(*, data_root: Path, scenario_key: str, payload: dict[str, Any]) -> Path:
    manifest_dir = data_root / "manifests"
    manifest_dir.mkdir(exist_ok=True)
    manifest_path = manifest_dir / f"{scenario_key}-{SCENARIO_VERSION}.json"
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return manifest_path


def seed_scenario(
    data_root: Path,
    scenario_key: str,
    *,
    runtime_environment: Optional[RuntimeEnvironment] = None,
    session_factory: Optional[Callable[[], Session]] = None,
    bind_host: str = "127.0.0.1",
) -> Path:
    """Seed a synthetic QA scenario into ``data_root`` and write its manifest."""
    scenario = SCENARIOS.get(scenario_key)
    if scenario is None:
        raise QaOpsError(
            f"Unknown QA scenario: {scenario_key}.",
            code="qa_scenario_unknown",
            status_code=404,
        )

    runtime_identity = runtime_environment or runtime_environment_from_env()
    require_qa_runtime(runtime_identity)

    resolved_data_root = bootstrap_data_root(data_root)
    try:
        materialize_vendor_synthetic_fixtures(resolved_data_root)
    except QaAssetError as exc:
        raise QaOpsError(str(exc), code="qa_assets_unavailable", status_code=500) from exc

    create_session = session_factory or _default_session_factory(resolved_data_root)
    with create_session() as session:
        seed_default_settings(session)
        seed_default_categories(session)
        context = SeedContext(
            session=session,
            data_root=resolved_data_root,
            runtime_environment=runtime_identity,
        )
        try:
            scenario_payload = scenario.seed(context)
        except (ImportValidationError, ReportingError) as exc:
            raise QaOpsError(f"{scenario_key} seed failed: {exc.message}", code=exc.code) from exc
        except QaAssetError as exc:
            raise QaOpsError(str(exc), code="qa_assets_unavailable", status_code=500) from exc

        runtime = status_payload(
            data_root=resolved_data_root,
            bind_host=bind_host,
            runtime_environment=runtime_identity,
        )
        payload = {
            "scenario": scenario_key,
            "scenario_version": SCENARIO_VERSION,
            "dataset_kind": runtime_identity.dataset_kind,
            "synthetic_artifact_marker": SYNTHETIC_ARTIFACT_MARKER,
            **scenario_payload,
            **_operator_state(session, runtime=runtime),
        }

    return _write_manifest(data_root=resolved_data_root, scenario_key=scenario_key, payload=payload)


def seed_baseline_scenario(data_root: Path, **kwargs: Any) -> Path:
    return seed_scenario(data_root, BASELINE_SCENARIO, **kwargs)


def latest_manifest(data_root: Path) -> Optional[dict[str, Any]]:
    """Return a compact summary of the most recently written scenario manifest."""
    manifest_dir = data_root / "manifests"
    if not manifest_dir.is_dir():
        return None
    manifests: Iterator[Path] = manifest_dir.glob("*.json")
    newest = max(manifests, key=lambda path: path.stat().st_mtime, default=None)
    if newest is None:
        return None
    payload = json.loads(newest.read_text(encoding="utf-8"))
    return {
        "manifest_file": newest.name,
        "scenario": payload.get("scenario"),
        "scenario_version": payload.get("scenario_version"),
        "description": payload.get("description"),
        "transactions": payload.get("transactions"),
        "validation_findings": payload.get("validation_findings"),
        "artifact_total": payload.get("artifact_total"),
    }

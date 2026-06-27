from contextlib import asynccontextmanager
from pathlib import Path
import os
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from family_finance_os import __version__
from family_finance_os.actors import ActorContext, actors_payload, derive_actor_context
from family_finance_os.category_service import (
    CategoryCreateRequest,
    CategoryError,
    CategoryPatchRequest,
    create_custom_category,
    list_categories,
    seed_default_categories,
    update_category,
)
from family_finance_os.database import create_sqlite_engine, resolve_database_path, upgrade_database
from family_finance_os.decision_events import (
    DecisionEventError,
    DecisionEventRequest,
)
from family_finance_os.approvals import (
    ApprovalActionRequest,
    ApprovalRequestCreate,
    ApprovalServiceError,
    approve_approval_request,
    cancel_approval_request,
    create_approval_request,
    is_approval_mode_enabled,
    list_approval_requests,
    reject_approval_request,
)
from family_finance_os.auth import (
    DevBypassRequest,
    LoginRequest,
    OwnerEnrollmentRequest,
    RecoveryLoginRequest,
    SESSION_ABSOLUTE_DAYS,
    SESSION_COOKIE_NAME,
    AuthError,
    any_users_exist,
    auth_status,
    create_dev_bypass_session,
    enroll_owner,
    login,
    logout,
    recovery_login,
    resolve_session,
)
from family_finance_os.elevated_mode import (
    ElevatedModeEnterRequest,
    ElevatedModeError,
    ElevatedModeExitRequest,
    ElevatedModeTouchRequest,
    current_elevated_session_id,
    elevated_mode_http_error,
    elevated_mode_metadata_payload,
    get_elevated_mode_registry,
    reset_elevated_mode_registry,
    reset_request_elevated_session_id,
    serialize_active_session,
    set_request_elevated_session_id,
)
from family_finance_os.funds import (
    ActorMutationRequest,
    BudgetTargetCreateRequest,
    BudgetTargetPatchRequest,
    FinancialGoalCreateRequest,
    FinancialGoalPatchRequest,
    FundCommitmentCreateRequest,
    FundCommitmentPatchRequest,
    FundPoolCreateRequest,
    FundPoolPatchRequest,
    FundsError,
    create_budget_target,
    create_financial_goal,
    create_fund_commitment,
    create_fund_pool,
    delete_fund_commitment,
    funds_summary,
    list_budget_targets,
    list_financial_goals,
    list_fund_commitments,
    list_fund_pools,
    update_budget_target,
    update_financial_goal,
    update_fund_commitment,
    update_fund_pool,
)
from family_finance_os.import_validation import (
    ImportValidationError,
    accept_import_batch,
    list_validation_findings,
    refresh_source_coverage_findings,
    resolve_validation_finding,
    save_upload,
    scan_inbox,
    serialize_import_batch,
    validate_import_batch,
    void_import_batch,
)
from family_finance_os.ledger_normalization import get_transaction, list_transactions
from family_finance_os.net_worth import (
    ActorNetWorthRequest,
    NetWorthError,
    NetWorthSnapshotCreateRequest,
    NetWorthSnapshotPatchRequest,
    accept_net_worth_import,
    create_net_worth_snapshot,
    delete_net_worth_snapshot,
    list_net_worth_snapshots,
    net_worth_summary,
    preview_net_worth_import,
    update_net_worth_snapshot,
)
from family_finance_os.operator_summary import operator_summary_payload
from family_finance_os.permissions import (
    ActionKey,
    DataScopeKey,
    PermissionDeniedError,
    PermissionEvaluation,
    PermissionEvaluator,
    PermissionPreviewRequest,
    actor_context_for_persona,
    effective_permission_payload,
)
from family_finance_os.suggestions import (
    SuggestionActionRequest,
    SuggestionCreate,
    SuggestionServiceError,
    accept_suggestion,
    convert_suggestion_to_approval,
    create_suggestion,
    dismiss_suggestion,
    list_suggestions,
    route_review_decide,
)
from family_finance_os.analyst_export import (
    AnalystExportRequest,
    analyst_pack_options,
    build_analyst_pack,
    list_analyst_pack_prompts,
)
from family_finance_os.dashboard import (
    DashboardError,
    dashboard_cashflow,
    dashboard_category_spend,
    dashboard_net_worth,
    dashboard_pool_progress,
    dashboard_summary,
)
from family_finance_os.reporting import (
    AdvisorExportRequest,
    MonthlyCloseRequest,
    ReportRunRequest,
    ReportingError,
    artifact_download_path,
    create_advisor_export,
    create_monthly_close,
    list_artifacts,
    run_reports,
)
from family_finance_os.runtime import RuntimeEnvironment, bootstrap_data_root, runtime_environment_from_env
from family_finance_os.settings_service import (
    SettingsPatchRequest,
    SettingsValidationError,
    apply_settings_patch,
    seed_default_settings,
    serialize_events,
    settings_payload,
)
from family_finance_os.spendable import SpendableError, compute_spendable
from family_finance_os.splits import (
    ReceiptPromotionRequest,
    SplitsError,
    TransactionAllocationsDeleteRequest,
    TransactionAllocationsPutRequest,
    delete_transaction_allocations,
    list_transaction_allocations,
    promote_receipt_lines_to_allocations,
    replace_transaction_allocations,
)


APP_NAME = "Family Finance OS"
STATIC_DIR = Path(__file__).resolve().parent / "static"
UI_SHELL_CACHE_HEADERS = {"Cache-Control": "no-cache, must-revalidate"}


class AcceptImportBatchRequest(BaseModel):
    acknowledge_warnings: bool = False
    actor: str = Field(default="owner", min_length=1)
    actor_context: Optional[ActorContext] = None


class VoidImportBatchRequest(BaseModel):
    actor: str = Field(min_length=1)
    actor_context: Optional[ActorContext] = None
    reason: str = Field(min_length=1)
    destroy_files: bool = False


class ResolveValidationFindingRequest(BaseModel):
    actor: str = Field(min_length=1)
    actor_context: Optional[ActorContext] = None
    note: str = Field(min_length=1)


def _default_data_root() -> Path:
    return Path(os.environ.get("DATA_ROOT", "/data")).expanduser().resolve()


def _database_status(data_root: Path) -> Dict[str, str]:
    database_path = resolve_database_path(data_root / "database")
    if database_path.exists():
        return {"status": "present", "path": str(database_path)}
    return {"status": "not_initialized", "path": str(database_path)}


def create_app(
    *,
    data_root: Optional[Path] = None,
    local_bind_host: Optional[str] = None,
    runtime_environment: Optional[RuntimeEnvironment] = None,
) -> FastAPI:
    configured_data_root = data_root or _default_data_root()
    resolved_data_root: Optional[Path] = None
    engine: Optional[Engine] = None
    bind_host = local_bind_host or os.environ.get("APP_BIND_HOST", "127.0.0.1")
    runtime_identity = runtime_environment or runtime_environment_from_env()

    def get_data_root() -> Path:
        nonlocal resolved_data_root
        if resolved_data_root is None:
            resolved_data_root = bootstrap_data_root(configured_data_root)
        return resolved_data_root

    def get_database_path() -> Path:
        return resolve_database_path(get_data_root() / "database")

    def get_engine() -> Engine:
        nonlocal engine
        if engine is None:
            database_path = get_database_path()
            upgrade_database(database_path)
            engine = create_sqlite_engine(database_path)
        return engine

    def create_session():
        Session = sessionmaker(bind=get_engine())
        return Session()

    def initialize_runtime_state() -> None:
        get_data_root()
        with create_session() as session:
            seed_default_settings(session)
            seed_default_categories(session)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        reset_elevated_mode_registry()
        initialize_runtime_state()
        yield

    app = FastAPI(title=APP_NAME, version=__version__, lifespan=lifespan)

    @app.middleware("http")
    async def elevated_session_middleware(request: Request, call_next):
        session_context = set_request_elevated_session_id(request.headers.get("X-Elevated-Session-Id"))
        try:
            return await call_next(request)
        finally:
            reset_request_elevated_session_id(session_context)

    def public_auth_path(path: str) -> bool:
        return (
            path in {"/api/health", "/api/status"}
            or path.startswith("/api/auth/")
            or path.startswith("/assets/")
            or not path.startswith("/api/")
        )

    @app.middleware("http")
    async def auth_session_middleware(request: Request, call_next):
        if public_auth_path(request.url.path):
            return await call_next(request)
        with create_session() as session:
            if not any_users_exist(session):
                return await call_next(request)
            resolved = resolve_session(
                session,
                session_token=request.cookies.get(SESSION_COOKIE_NAME),
                client_host=request.client.host if request.client else "unknown",
            )
            if resolved is None:
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": {
                            "code": "authentication_required",
                            "message": "Authentication is required for this API route.",
                        }
                    },
                )
            request.state.auth_actor_context = resolved["actor_context"]
            request.state.auth_user = resolved["user"]
        return await call_next(request)

    def status_payload() -> Dict[str, Any]:
        active_data_root = get_data_root()
        return {
            "app": APP_NAME,
            "version": __version__,
            "local_only": bind_host == "127.0.0.1",
            "bind_host": bind_host,
            **runtime_identity.to_status_fields(),
            "data_root": {
                "path": str(active_data_root),
                "exists": active_data_root.exists(),
            },
            "database": _database_status(active_data_root),
        }

    @app.get("/api/health")
    def health() -> Dict[str, Any]:
        return status_payload()

    @app.get("/api/status")
    def status() -> Dict[str, Any]:
        return status_payload()

    def auth_http_error(exc: AuthError) -> HTTPException:
        return HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message})

    def auth_bypass_allowed() -> bool:
        return runtime_identity.qa_controls_enabled and bind_host == "127.0.0.1"

    def set_session_cookie(response, session_token: str, request: Request) -> None:
        response.set_cookie(
            SESSION_COOKIE_NAME,
            session_token,
            max_age=SESSION_ABSOLUTE_DAYS * 24 * 60 * 60,
            httponly=True,
            samesite="strict",
            secure=request.url.scheme == "https",
            path="/",
        )

    def clear_session_cookie(response) -> None:
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")

    @app.get("/api/auth/status")
    def get_auth_status(request: Request) -> Dict[str, Any]:
        with create_session() as session:
            return auth_status(
                session,
                session_token=request.cookies.get(SESSION_COOKIE_NAME),
                client_host=request.client.host if request.client else "unknown",
                qa_auth_bypass_available=auth_bypass_allowed(),
            )

    @app.post("/api/auth/enroll-owner")
    def post_auth_enroll_owner(payload: OwnerEnrollmentRequest, request: Request):
        if bind_host != "127.0.0.1":
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "local_session_required",
                    "message": "Owner enrollment can only create sessions on localhost-bound runtimes.",
                },
            )
        with create_session() as session:
            try:
                result = enroll_owner(
                    session,
                    payload,
                    client_host=request.client.host if request.client else "unknown",
                )
            except AuthError as exc:
                raise auth_http_error(exc) from exc
        if result.get("status") == "totp_confirmation_required":
            return JSONResponse(status_code=202, content=result)
        session_token = result.pop("session_token")
        response = JSONResponse(content=result)
        set_session_cookie(response, session_token, request)
        return response

    @app.post("/api/auth/login")
    def post_auth_login(payload: LoginRequest, request: Request):
        if bind_host != "127.0.0.1":
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "local_session_required",
                    "message": "Login can only create sessions on localhost-bound runtimes.",
                },
            )
        with create_session() as session:
            try:
                result = login(
                    session,
                    payload,
                    client_host=request.client.host if request.client else "unknown",
                )
            except AuthError as exc:
                raise auth_http_error(exc) from exc
        session_token = result.pop("session_token")
        response = JSONResponse(content=result)
        set_session_cookie(response, session_token, request)
        return response

    @app.post("/api/auth/recovery-login")
    def post_auth_recovery_login(payload: RecoveryLoginRequest, request: Request):
        if bind_host != "127.0.0.1":
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "local_session_required",
                    "message": "Recovery login can only create sessions on localhost-bound runtimes.",
                },
            )
        with create_session() as session:
            try:
                result = recovery_login(
                    session,
                    payload,
                    client_host=request.client.host if request.client else "unknown",
                )
            except AuthError as exc:
                raise auth_http_error(exc) from exc
        session_token = result.pop("session_token")
        response = JSONResponse(content=result)
        set_session_cookie(response, session_token, request)
        return response

    @app.post("/api/auth/logout")
    def post_auth_logout(request: Request):
        with create_session() as session:
            logout(session, session_token=request.cookies.get(SESSION_COOKIE_NAME))
        response = JSONResponse(content={"authenticated": False})
        clear_session_cookie(response)
        return response

    @app.post("/api/auth/dev-bypass")
    def post_auth_dev_bypass(payload: DevBypassRequest, request: Request):
        with create_session() as session:
            try:
                result = create_dev_bypass_session(
                    session,
                    payload,
                    client_host=request.client.host if request.client else "unknown",
                    allowed=auth_bypass_allowed(),
                )
            except AuthError as exc:
                raise auth_http_error(exc) from exc
        session_token = result.pop("session_token")
        response = JSONResponse(content=result)
        set_session_cookie(response, session_token, request)
        return response

    @app.get("/api/operator-summary")
    def operator_summary() -> Dict[str, Any]:
        with create_session() as session:
            refresh_source_coverage_findings(session)
            session.commit()
            return operator_summary_payload(session, runtime=status_payload())

    def spendable_http_error(exc: SpendableError) -> HTTPException:
        return HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message})

    def net_worth_http_error(exc: NetWorthError) -> HTTPException:
        return HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, **exc.detail},
        )

    @app.get("/api/spendable")
    def get_spendable(
        month: Optional[str] = Query(default=None),
        include_provisional: Optional[bool] = Query(default=None),
        persist_snapshot: bool = Query(default=False),
        snapshot_type: str = Query(default="draft_close"),
        monthly_close_id: Optional[str] = Query(default=None),
    ) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return compute_spendable(
                    session,
                    month=month,
                    include_provisional=include_provisional,
                    persist_snapshot=persist_snapshot,
                    snapshot_type=snapshot_type,
                    monthly_close_id=monthly_close_id,
                )
            except SpendableError as exc:
                raise spendable_http_error(exc) from exc

    @app.get("/api/net-worth/snapshots")
    def get_net_worth_snapshots(
        from_date: Optional[str] = Query(default=None, alias="from"),
        to_date: Optional[str] = Query(default=None, alias="to"),
    ) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return {"snapshots": list_net_worth_snapshots(session, from_date=from_date, to_date=to_date)}
            except NetWorthError as exc:
                raise net_worth_http_error(exc) from exc

    @app.post("/api/net-worth/snapshots")
    def post_net_worth_snapshot(payload: NetWorthSnapshotCreateRequest) -> Dict[str, Any]:
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.REVIEW_DECIDE,
                DataScopeKey.REVIEW_DECISIONS,
                actor_context=payload.actor_context,
            )
            try:
                return {"snapshot": create_net_worth_snapshot(session, payload)}
            except NetWorthError as exc:
                raise net_worth_http_error(exc) from exc

    @app.patch("/api/net-worth/snapshots/{snapshot_id}")
    def patch_net_worth_snapshot(snapshot_id: str, payload: NetWorthSnapshotPatchRequest) -> Dict[str, Any]:
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.REVIEW_DECIDE,
                DataScopeKey.REVIEW_DECISIONS,
                actor_context=payload.actor_context,
            )
            try:
                return {"snapshot": update_net_worth_snapshot(session, snapshot_id, payload)}
            except NetWorthError as exc:
                raise net_worth_http_error(exc) from exc

    @app.delete("/api/net-worth/snapshots/{snapshot_id}")
    def delete_net_worth_snapshot_route(snapshot_id: str, payload: ActorNetWorthRequest) -> Dict[str, Any]:
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.REVIEW_DECIDE,
                DataScopeKey.REVIEW_DECISIONS,
                actor_context=payload.actor_context,
            )
            try:
                return delete_net_worth_snapshot(session, snapshot_id, payload)
            except NetWorthError as exc:
                raise net_worth_http_error(exc) from exc

    @app.post("/api/net-worth/imports")
    async def post_net_worth_import(
        file: UploadFile = File(...),
        actor: Optional[str] = Form(default="owner"),
        actor_context_json: Optional[str] = Form(default=None),
    ) -> Dict[str, Any]:
        actor_context = (
            ActorContext.model_validate_json(actor_context_json) if actor_context_json else None
        )
        active_data_root = get_data_root()
        with create_session() as session:
            require_permission(
                session,
                actor or "owner",
                ActionKey.IMPORTS_RUN,
                DataScopeKey.IMPORTED_SOURCE_RECORDS,
                actor_context=actor_context,
            )
            try:
                preview = preview_net_worth_import(
                    active_data_root,
                    filename=file.filename or "SYNTHETIC_net_worth.csv",
                    content=await file.read(),
                    actor=actor or "owner",
                    actor_context=actor_context,
                )
                return {"import": preview}
            except NetWorthError as exc:
                raise net_worth_http_error(exc) from exc

    @app.post("/api/net-worth/imports/{import_id}/accept")
    def post_net_worth_import_accept(import_id: str, payload: ActorNetWorthRequest) -> Dict[str, Any]:
        active_data_root = get_data_root()
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.IMPORTS_RUN,
                DataScopeKey.IMPORTED_SOURCE_RECORDS,
                actor_context=payload.actor_context,
            )
            try:
                return accept_net_worth_import(session, active_data_root, import_id, payload)
            except NetWorthError as exc:
                raise net_worth_http_error(exc) from exc

    @app.get("/api/net-worth/summary")
    def get_net_worth_summary(
        from_date: Optional[str] = Query(default=None, alias="from"),
        to_date: Optional[str] = Query(default=None, alias="to"),
        include_estimates: bool = Query(default=False),
    ) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return net_worth_summary(
                    session,
                    from_date=from_date,
                    to_date=to_date,
                    include_estimates=include_estimates,
                )
            except NetWorthError as exc:
                raise net_worth_http_error(exc) from exc

    def funds_http_error(exc: FundsError) -> HTTPException:
        return HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message})

    @app.get("/api/funds/summary")
    def get_funds_summary(month: Optional[str] = Query(default=None)) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return funds_summary(session, month=month)
            except FundsError as exc:
                raise funds_http_error(exc) from exc
            except SpendableError as exc:
                raise spendable_http_error(exc) from exc

    @app.get("/api/fund-pools")
    def get_fund_pools(month: Optional[str] = Query(default=None)) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return {"pools": list_fund_pools(session, month=month)}
            except FundsError as exc:
                raise funds_http_error(exc) from exc

    @app.post("/api/fund-pools")
    def post_fund_pool(payload: FundPoolCreateRequest) -> Dict[str, Any]:
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.REVIEW_DECIDE,
                DataScopeKey.REVIEW_DECISIONS,
                actor_context=payload.actor_context,
            )
            try:
                return {"pool": create_fund_pool(session, payload)}
            except FundsError as exc:
                raise funds_http_error(exc) from exc

    @app.patch("/api/fund-pools/{pool_id}")
    def patch_fund_pool(pool_id: str, payload: FundPoolPatchRequest) -> Dict[str, Any]:
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.REVIEW_DECIDE,
                DataScopeKey.REVIEW_DECISIONS,
                actor_context=payload.actor_context,
            )
            try:
                return {"pool": update_fund_pool(session, pool_id, payload)}
            except FundsError as exc:
                raise funds_http_error(exc) from exc

    @app.get("/api/fund-commitments")
    def get_fund_commitments(month: Optional[str] = Query(default=None)) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return {"commitments": list_fund_commitments(session, month=month)}
            except FundsError as exc:
                raise funds_http_error(exc) from exc

    @app.post("/api/fund-commitments")
    def post_fund_commitment(payload: FundCommitmentCreateRequest) -> Dict[str, Any]:
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.REVIEW_DECIDE,
                DataScopeKey.REVIEW_DECISIONS,
                actor_context=payload.actor_context,
            )
            try:
                return {"commitment": create_fund_commitment(session, payload)}
            except FundsError as exc:
                raise funds_http_error(exc) from exc

    @app.patch("/api/fund-commitments/{commitment_id}")
    def patch_fund_commitment(commitment_id: str, payload: FundCommitmentPatchRequest) -> Dict[str, Any]:
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.REVIEW_DECIDE,
                DataScopeKey.REVIEW_DECISIONS,
                actor_context=payload.actor_context,
            )
            try:
                return {"commitment": update_fund_commitment(session, commitment_id, payload)}
            except FundsError as exc:
                raise funds_http_error(exc) from exc

    @app.delete("/api/fund-commitments/{commitment_id}")
    def delete_fund_commitment_route(commitment_id: str, payload: ActorMutationRequest) -> Dict[str, Any]:
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.REVIEW_DECIDE,
                DataScopeKey.REVIEW_DECISIONS,
                actor_context=payload.actor_context,
            )
            try:
                return {"commitment": delete_fund_commitment(session, commitment_id, payload)}
            except FundsError as exc:
                raise funds_http_error(exc) from exc

    @app.get("/api/financial-goals")
    def get_financial_goals() -> Dict[str, Any]:
        with create_session() as session:
            return {"goals": list_financial_goals(session)}

    @app.post("/api/financial-goals")
    def post_financial_goal(payload: FinancialGoalCreateRequest) -> Dict[str, Any]:
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.REVIEW_DECIDE,
                DataScopeKey.REVIEW_DECISIONS,
                actor_context=payload.actor_context,
            )
            try:
                return {"goal": create_financial_goal(session, payload)}
            except FundsError as exc:
                raise funds_http_error(exc) from exc

    @app.patch("/api/financial-goals/{goal_id}")
    def patch_financial_goal(goal_id: str, payload: FinancialGoalPatchRequest) -> Dict[str, Any]:
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.REVIEW_DECIDE,
                DataScopeKey.REVIEW_DECISIONS,
                actor_context=payload.actor_context,
            )
            try:
                return {"goal": update_financial_goal(session, goal_id, payload)}
            except FundsError as exc:
                raise funds_http_error(exc) from exc

    @app.get("/api/budget-targets")
    def get_budget_targets(month: Optional[str] = Query(default=None)) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return {"budget_targets": list_budget_targets(session, month=month)}
            except FundsError as exc:
                raise funds_http_error(exc) from exc

    @app.post("/api/budget-targets")
    def post_budget_target(payload: BudgetTargetCreateRequest) -> Dict[str, Any]:
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.REVIEW_DECIDE,
                DataScopeKey.REVIEW_DECISIONS,
                actor_context=payload.actor_context,
            )
            try:
                return {"budget_target": create_budget_target(session, payload)}
            except FundsError as exc:
                raise funds_http_error(exc) from exc

    @app.patch("/api/budget-targets/{target_id}")
    def patch_budget_target(target_id: str, payload: BudgetTargetPatchRequest) -> Dict[str, Any]:
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.REVIEW_DECIDE,
                DataScopeKey.REVIEW_DECISIONS,
                actor_context=payload.actor_context,
            )
            try:
                return {"budget_target": update_budget_target(session, target_id, payload)}
            except FundsError as exc:
                raise funds_http_error(exc) from exc

    @app.get("/api/actors")
    def get_actors() -> Dict[str, Any]:
        return actors_payload()

    def permission_http_error(exc: PermissionDeniedError) -> HTTPException:
        return HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "message": exc.message,
                "suggestion_allowed": exc.suggestion_allowed,
            },
        )

    def require_permission(
        session,
        actor: str,
        action_key: ActionKey,
        data_scope_key: DataScopeKey,
        *,
        actor_context: Optional[ActorContext] = None,
    ) -> None:
        registry = get_elevated_mode_registry()
        elevated_session = registry.get_active(
            session,
            session_id=current_elevated_session_id(),
        )
        try:
            PermissionEvaluator(session).require(
                actor,
                action_key,
                data_scope_key,
                actor_context=actor_context,
                elevated_session=elevated_session,
            )
        except PermissionDeniedError as exc:
            raise permission_http_error(exc) from exc

    def resolve_actor_context(
        actor: Optional[str],
        actor_context_header: Optional[str],
        actor_context: Optional[ActorContext] = None,
    ) -> tuple[str, Optional[ActorContext]]:
        resolved_actor = actor or "owner"
        if actor_context is not None:
            return resolved_actor, actor_context
        if actor_context_header:
            return resolved_actor, ActorContext.model_validate_json(actor_context_header)
        return resolved_actor, None

    @app.get("/api/permissions/effective")
    def get_effective_permission(
        action_key: str = Query(..., min_length=1),
        data_scope_key: str = Query(..., min_length=1),
        actor: Optional[str] = Query(default=None),
        x_actor_context: Optional[str] = Header(default=None, alias="X-Actor-Context"),
    ) -> Dict[str, Any]:
        resolved_actor, resolved_context = resolve_actor_context(actor, x_actor_context)
        with create_session() as session:
            evaluator = PermissionEvaluator(session)
            evaluation = evaluator.evaluate(
                derive_actor_context(resolved_actor, resolved_context),
                action_key,
                data_scope_key,
            )
            return effective_permission_payload(evaluation)

    @app.post("/api/permissions/preview")
    def preview_permission(payload: PermissionPreviewRequest) -> Dict[str, Any]:
        if not (runtime_identity.qa_controls_enabled or runtime_identity.dev_mode):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "permission_preview_unavailable",
                    "message": "Permission preview is available only in QA or dev mode.",
                },
            )
        try:
            preview_context = actor_context_for_persona(payload.persona_key)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "unknown_persona_key", "message": str(exc)},
            ) from exc

        with create_session() as session:
            evaluator = PermissionEvaluator(session)
            evaluation = evaluator.evaluate(
                preview_context,
                payload.action_key,
                payload.data_scope_key,
                scope_selector=payload.scope_selector,
            )
            return {
                "persona_key": payload.persona_key,
                **effective_permission_payload(evaluation),
            }

    def elevated_mode_error_http(exc: ElevatedModeError) -> HTTPException:
        return HTTPException(status_code=exc.status_code, detail=elevated_mode_http_error(exc))

    @app.get("/api/elevated-mode/status")
    def get_elevated_mode_status(
        x_elevated_session_id: Optional[str] = Header(default=None, alias="X-Elevated-Session-Id"),
    ) -> Dict[str, Any]:
        registry = get_elevated_mode_registry()
        with create_session() as session:
            return registry.status(session, x_elevated_session_id)

    @app.post("/api/elevated-mode/enter")
    def post_elevated_mode_enter(
        payload: ElevatedModeEnterRequest,
        has_unsaved_edits: bool = Query(default=False),
        x_elevated_session_id: Optional[str] = Header(default=None, alias="X-Elevated-Session-Id"),
    ) -> Dict[str, Any]:
        registry = get_elevated_mode_registry()
        with create_session() as session:
            try:
                active = registry.enter(
                    session,
                    payload,
                    session_id=x_elevated_session_id,
                    has_unsaved_edits=has_unsaved_edits,
                )
            except ElevatedModeError as exc:
                raise elevated_mode_error_http(exc) from exc
            return {**serialize_active_session(active), **elevated_mode_metadata_payload()}

    @app.post("/api/elevated-mode/exit")
    def post_elevated_mode_exit(
        payload: ElevatedModeExitRequest,
        x_elevated_session_id: Optional[str] = Header(default=None, alias="X-Elevated-Session-Id"),
    ) -> Dict[str, Any]:
        if not x_elevated_session_id:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "elevated_session_id_required",
                    "message": "X-Elevated-Session-Id header is required to exit elevated mode.",
                },
            )
        registry = get_elevated_mode_registry()
        with create_session() as session:
            try:
                registry.exit(session, x_elevated_session_id, payload)
            except ElevatedModeError as exc:
                raise elevated_mode_error_http(exc) from exc
            return {"active": False}

    @app.post("/api/elevated-mode/touch")
    def post_elevated_mode_touch(
        payload: ElevatedModeTouchRequest,
        x_elevated_session_id: Optional[str] = Header(default=None, alias="X-Elevated-Session-Id"),
    ) -> Dict[str, Any]:
        if not x_elevated_session_id:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "elevated_session_id_required",
                    "message": "X-Elevated-Session-Id header is required to touch elevated mode.",
                },
            )
        registry = get_elevated_mode_registry()
        with create_session() as session:
            try:
                active = registry.touch(session, x_elevated_session_id, payload)
            except ElevatedModeError as exc:
                raise elevated_mode_error_http(exc) from exc
            return serialize_active_session(active)

    def import_validation_http_error(exc: ImportValidationError) -> HTTPException:
        return HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        )

    @app.get("/api/inbox/scan")
    def get_inbox_scan() -> Dict[str, Any]:
        active_data_root = get_data_root()
        with create_session() as session:
            return {
                "import_batches": [
                    serialize_import_batch(batch) for batch in scan_inbox(session, active_data_root)
                ]
            }

    @app.post("/api/inbox/scan")
    def post_inbox_scan() -> Dict[str, Any]:
        active_data_root = get_data_root()
        with create_session() as session:
            return {
                "import_batches": [
                    serialize_import_batch(batch) for batch in scan_inbox(session, active_data_root)
                ]
            }

    @app.post("/api/uploads")
    async def upload_source_file(
        file: UploadFile = File(...),
        source_key: Optional[str] = Form(default=None),
        actor: Optional[str] = Form(default="owner"),
        actor_context_json: Optional[str] = Form(default=None),
    ) -> Dict[str, Any]:
        active_data_root = get_data_root()
        filename = file.filename or "uploaded-file"
        content = await file.read()
        actor_context = (
            ActorContext.model_validate_json(actor_context_json) if actor_context_json else None
        )
        with create_session() as session:
            require_permission(
                session,
                actor or "owner",
                ActionKey.IMPORTS_RUN,
                DataScopeKey.IMPORTED_SOURCE_RECORDS,
                actor_context=actor_context,
            )
            try:
                batch = save_upload(session, active_data_root, filename, content, source_key_hint=source_key)
                return {"import_batch": serialize_import_batch(batch)}
            except ImportValidationError as exc:
                raise import_validation_http_error(exc) from exc

    @app.post("/api/import-batches/{batch_id}/validate")
    def validate_batch(batch_id: str) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return validate_import_batch(session, batch_id)
            except ImportValidationError as exc:
                raise import_validation_http_error(exc) from exc

    @app.post("/api/import-batches/{batch_id}/accept")
    def accept_batch(
        batch_id: str,
        payload: Optional[AcceptImportBatchRequest] = None,
    ) -> Dict[str, Any]:
        active_data_root = get_data_root()
        request_payload = payload or AcceptImportBatchRequest()
        with create_session() as session:
            require_permission(
                session,
                request_payload.actor,
                ActionKey.IMPORTS_RUN,
                DataScopeKey.IMPORTED_SOURCE_RECORDS,
                actor_context=request_payload.actor_context,
            )
            try:
                return accept_import_batch(
                    session,
                    active_data_root,
                    batch_id,
                    acknowledge_warnings=request_payload.acknowledge_warnings,
                )
            except ImportValidationError as exc:
                raise import_validation_http_error(exc) from exc

    @app.post("/api/import-batches/{batch_id}/void")
    def void_batch(batch_id: str, payload: VoidImportBatchRequest) -> Dict[str, Any]:
        active_data_root = get_data_root()
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.IMPORTS_RUN,
                DataScopeKey.IMPORTED_SOURCE_RECORDS,
                actor_context=payload.actor_context,
            )
            try:
                return void_import_batch(
                    session,
                    active_data_root,
                    batch_id,
                    actor=payload.actor,
                    actor_context=payload.actor_context,
                    reason=payload.reason,
                    destroy_files=payload.destroy_files,
                )
            except ImportValidationError as exc:
                raise import_validation_http_error(exc) from exc

    @app.get("/api/validation-findings")
    def get_validation_findings() -> Dict[str, Any]:
        with create_session() as session:
            return {"findings": list_validation_findings(session)}

    @app.post("/api/validation-findings/{finding_id}/resolve")
    def resolve_finding(finding_id: str, payload: ResolveValidationFindingRequest) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return resolve_validation_finding(
                    session,
                    finding_id,
                    actor=payload.actor,
                    actor_context=payload.actor_context,
                    note=payload.note,
                )
            except ImportValidationError as exc:
                raise import_validation_http_error(exc) from exc

    @app.get("/api/transactions")
    def get_transactions() -> Dict[str, Any]:
        with create_session() as session:
            return {"transactions": list_transactions(session)}

    @app.get("/api/transactions/{transaction_id}")
    def get_transaction_detail(transaction_id: str) -> Dict[str, Any]:
        with create_session() as session:
            transaction = get_transaction(session, transaction_id)
            if transaction is None:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "transaction_not_found", "message": "Transaction not found"},
                )
            return {"transaction": transaction}

    def splits_http_error(exc: SplitsError) -> HTTPException:
        return HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message})

    @app.get("/api/transactions/{transaction_id}/allocations")
    def get_transaction_allocations(transaction_id: str) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return list_transaction_allocations(session, transaction_id)
            except SplitsError as exc:
                raise splits_http_error(exc) from exc

    @app.put("/api/transactions/{transaction_id}/allocations")
    def put_transaction_allocations(transaction_id: str, payload: TransactionAllocationsPutRequest) -> Dict[str, Any]:
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.REVIEW_DECIDE,
                DataScopeKey.REVIEW_DECISIONS,
                actor_context=payload.actor_context,
            )
            try:
                return replace_transaction_allocations(session, transaction_id, payload)
            except SplitsError as exc:
                raise splits_http_error(exc) from exc

    @app.delete("/api/transactions/{transaction_id}/allocations")
    def delete_transaction_allocations_route(
        transaction_id: str,
        payload: TransactionAllocationsDeleteRequest,
    ) -> Dict[str, Any]:
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.REVIEW_DECIDE,
                DataScopeKey.REVIEW_DECISIONS,
                actor_context=payload.actor_context,
            )
            try:
                return delete_transaction_allocations(session, transaction_id, payload)
            except SplitsError as exc:
                raise splits_http_error(exc) from exc

    @app.post("/api/transactions/{transaction_id}/allocations/from-receipt")
    def post_transaction_allocations_from_receipt(
        transaction_id: str,
        payload: ReceiptPromotionRequest,
    ) -> Dict[str, Any]:
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.REVIEW_DECIDE,
                DataScopeKey.REVIEW_DECISIONS,
                actor_context=payload.actor_context,
            )
            try:
                return promote_receipt_lines_to_allocations(session, transaction_id, payload)
            except SplitsError as exc:
                raise splits_http_error(exc) from exc

    @app.post("/api/decision-events")
    def post_decision_event(payload: DecisionEventRequest) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return route_review_decide(session, payload)
            except PermissionDeniedError as exc:
                raise permission_http_error(exc) from exc
            except DecisionEventError as exc:
                raise HTTPException(
                    status_code=exc.status_code,
                    detail={"code": exc.code, "message": exc.message},
                ) from exc
            except (ApprovalServiceError, SuggestionServiceError) as exc:
                raise HTTPException(
                    status_code=exc.status_code,
                    detail={"code": exc.code, "message": exc.message},
                ) from exc

    def require_review_suggest_or_decide(
        session,
        actor: str,
        actor_context: Optional[ActorContext],
    ) -> PermissionEvaluation:
        evaluator = PermissionEvaluator(session)
        evaluation = evaluator.evaluate(
            derive_actor_context(actor, actor_context),
            ActionKey.REVIEW_DECIDE.value,
            DataScopeKey.REVIEW_DECISIONS.value,
        )
        if evaluation.allowed or evaluation.suggestion_allowed:
            return evaluation
        raise PermissionDeniedError(
            ActionKey.REVIEW_DECIDE.value,
            DataScopeKey.REVIEW_DECISIONS.value,
            suggestion_allowed=False,
        )

    @app.get("/api/suggestions")
    def get_suggestions(
        status: Optional[str] = Query(default=None),
        target_id: Optional[str] = Query(default=None),
        actor: Optional[str] = Query(default="owner"),
        x_actor_context: Optional[str] = Header(default=None, alias="X-Actor-Context"),
    ) -> Dict[str, Any]:
        resolved_actor, resolved_context = resolve_actor_context(actor, x_actor_context)
        with create_session() as session:
            require_permission(
                session,
                resolved_actor,
                ActionKey.TRANSACTIONS_VIEW,
                DataScopeKey.CANONICAL_TRANSACTIONS,
                actor_context=resolved_context,
            )
            return list_suggestions(session, status=status, target_id=target_id)

    @app.post("/api/suggestions")
    def post_suggestion(payload: SuggestionCreate) -> Dict[str, Any]:
        with create_session() as session:
            try:
                require_review_suggest_or_decide(session, payload.actor, payload.actor_context)
                return create_suggestion(session, payload)
            except PermissionDeniedError as exc:
                raise permission_http_error(exc) from exc
            except SuggestionServiceError as exc:
                raise HTTPException(
                    status_code=exc.status_code,
                    detail={"code": exc.code, "message": exc.message},
                ) from exc

    @app.post("/api/suggestions/{suggestion_id}/dismiss")
    def post_suggestion_dismiss(
        suggestion_id: str,
        payload: SuggestionActionRequest,
    ) -> Dict[str, Any]:
        with create_session() as session:
            try:
                require_review_suggest_or_decide(session, payload.actor, payload.actor_context)
                return dismiss_suggestion(session, suggestion_id, payload)
            except PermissionDeniedError as exc:
                raise permission_http_error(exc) from exc
            except SuggestionServiceError as exc:
                raise HTTPException(
                    status_code=exc.status_code,
                    detail={"code": exc.code, "message": exc.message},
                ) from exc

    @app.post("/api/suggestions/{suggestion_id}/accept")
    def post_suggestion_accept(
        suggestion_id: str,
        payload: SuggestionActionRequest,
    ) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return accept_suggestion(session, suggestion_id, payload)
            except SuggestionServiceError as exc:
                raise HTTPException(
                    status_code=exc.status_code,
                    detail={"code": exc.code, "message": exc.message},
                ) from exc
            except DecisionEventError as exc:
                raise HTTPException(
                    status_code=exc.status_code,
                    detail={"code": exc.code, "message": exc.message},
                ) from exc

    @app.post("/api/suggestions/{suggestion_id}/convert-to-approval")
    def post_suggestion_convert_to_approval(
        suggestion_id: str,
        payload: SuggestionActionRequest,
    ) -> Dict[str, Any]:
        with create_session() as session:
            if not is_approval_mode_enabled(session):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "approval_mode_disabled",
                        "message": "Approval management is unavailable while approval mode is disabled.",
                    },
                )
            try:
                require_review_suggest_or_decide(session, payload.actor, payload.actor_context)
                return convert_suggestion_to_approval(session, suggestion_id, payload)
            except PermissionDeniedError as exc:
                raise permission_http_error(exc) from exc
            except (SuggestionServiceError, ApprovalServiceError) as exc:
                raise HTTPException(
                    status_code=exc.status_code,
                    detail={"code": exc.code, "message": exc.message},
                ) from exc

    @app.get("/api/approval-requests")
    def get_approval_requests(
        status: Optional[str] = Query(default=None),
        target_id: Optional[str] = Query(default=None),
    ) -> Dict[str, Any]:
        with create_session() as session:
            if not is_approval_mode_enabled(session):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "approval_mode_disabled",
                        "message": "Approval management is unavailable while approval mode is disabled.",
                    },
                )
            return list_approval_requests(session, status=status, target_id=target_id)

    @app.post("/api/approval-requests")
    def post_approval_request(payload: ApprovalRequestCreate) -> Dict[str, Any]:
        with create_session() as session:
            if not is_approval_mode_enabled(session):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "approval_mode_disabled",
                        "message": "Approval management is unavailable while approval mode is disabled.",
                    },
                )
            try:
                require_review_suggest_or_decide(session, payload.actor, payload.actor_context)
                return create_approval_request(session, payload)
            except PermissionDeniedError as exc:
                raise permission_http_error(exc) from exc
            except ApprovalServiceError as exc:
                raise HTTPException(
                    status_code=exc.status_code,
                    detail={"code": exc.code, "message": exc.message},
                ) from exc

    @app.post("/api/approval-requests/{approval_request_id}/approve")
    def post_approval_request_approve(
        approval_request_id: str,
        payload: ApprovalActionRequest,
    ) -> Dict[str, Any]:
        with create_session() as session:
            if not is_approval_mode_enabled(session):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "approval_mode_disabled",
                        "message": "Approval management is unavailable while approval mode is disabled.",
                    },
                )
            require_permission(
                session,
                payload.actor,
                ActionKey.REVIEW_DECIDE,
                DataScopeKey.REVIEW_DECISIONS,
                actor_context=payload.actor_context,
            )
            try:
                return approve_approval_request(session, approval_request_id, payload)
            except ApprovalServiceError as exc:
                raise HTTPException(
                    status_code=exc.status_code,
                    detail={"code": exc.code, "message": exc.message},
                ) from exc
            except DecisionEventError as exc:
                raise HTTPException(
                    status_code=exc.status_code,
                    detail={"code": exc.code, "message": exc.message},
                ) from exc

    @app.post("/api/approval-requests/{approval_request_id}/reject")
    def post_approval_request_reject(
        approval_request_id: str,
        payload: ApprovalActionRequest,
    ) -> Dict[str, Any]:
        with create_session() as session:
            if not is_approval_mode_enabled(session):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "approval_mode_disabled",
                        "message": "Approval management is unavailable while approval mode is disabled.",
                    },
                )
            require_permission(
                session,
                payload.actor,
                ActionKey.REVIEW_DECIDE,
                DataScopeKey.REVIEW_DECISIONS,
                actor_context=payload.actor_context,
            )
            try:
                return reject_approval_request(session, approval_request_id, payload)
            except ApprovalServiceError as exc:
                raise HTTPException(
                    status_code=exc.status_code,
                    detail={"code": exc.code, "message": exc.message},
                ) from exc

    @app.post("/api/approval-requests/{approval_request_id}/cancel")
    def post_approval_request_cancel(
        approval_request_id: str,
        payload: ApprovalActionRequest,
    ) -> Dict[str, Any]:
        with create_session() as session:
            if not is_approval_mode_enabled(session):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "approval_mode_disabled",
                        "message": "Approval management is unavailable while approval mode is disabled.",
                    },
                )
            try:
                return cancel_approval_request(session, approval_request_id, payload)
            except ApprovalServiceError as exc:
                raise HTTPException(
                    status_code=exc.status_code,
                    detail={"code": exc.code, "message": exc.message},
                ) from exc

    @app.get("/api/settings")
    def get_settings() -> Dict[str, Any]:
        active_data_root = get_data_root()
        with create_session() as session:
            return settings_payload(
                session,
                data_root=active_data_root,
                local_only=bind_host == "127.0.0.1",
                runtime=status_payload(),
            )

    @app.patch("/api/settings")
    def patch_settings(payload: SettingsPatchRequest) -> Dict[str, Any]:
        active_data_root = get_data_root()
        with create_session() as session:
            source_domains = {"sources", "source_profiles"}
            approval_domains = {"approval"}
            if any(change.domain in source_domains for change in payload.changes):
                require_permission(
                    session,
                    payload.actor,
                    ActionKey.IMPORTS_SETTINGS_CONFIGURE,
                    DataScopeKey.SOURCE_PROFILES_IMPORT_CONFIG,
                    actor_context=payload.actor_context,
                )
            elif all(change.domain in approval_domains for change in payload.changes):
                require_permission(
                    session,
                    payload.actor,
                    ActionKey.APPROVAL_RULES_CONFIGURE,
                    DataScopeKey.APPROVAL_RULE_CONFIGURATION,
                    actor_context=payload.actor_context,
                )
            else:
                require_permission(
                    session,
                    payload.actor,
                    ActionKey.RUNTIME_SETTINGS_MANAGE,
                    DataScopeKey.RUNTIME_SETTINGS,
                    actor_context=payload.actor_context,
                )
            try:
                events = apply_settings_patch(session, payload)
                refresh_source_coverage_findings(session)
                session.commit()
                return {
                    **settings_payload(
                        session,
                        data_root=active_data_root,
                        local_only=bind_host == "127.0.0.1",
                        runtime=status_payload(),
                    ),
                    "events": serialize_events(events),
                }
            except SettingsValidationError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=[{"code": exc.code, "message": exc.message}],
                ) from exc

    def category_http_error(exc: CategoryError) -> HTTPException:
        return HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        )

    @app.get("/api/categories")
    def get_categories() -> Dict[str, Any]:
        with create_session() as session:
            return {"categories": list_categories(session)}

    @app.post("/api/categories")
    def post_category(payload: CategoryCreateRequest) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return {"category": create_custom_category(session, payload)}
            except CategoryError as exc:
                raise category_http_error(exc) from exc

    @app.patch("/api/categories/{category_key}")
    def patch_category(category_key: str, payload: CategoryPatchRequest) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return {"category": update_category(session, category_key, payload)}
            except CategoryError as exc:
                raise category_http_error(exc) from exc

    def reporting_http_error(exc: ReportingError) -> HTTPException:
        return HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, **exc.detail},
        )

    @app.post("/api/reports/run")
    def post_reports_run(payload: ReportRunRequest) -> Dict[str, Any]:
        active_data_root = get_data_root()
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.REPORTS_GENERATE,
                DataScopeKey.REPORTS_DASHBOARDS,
                actor_context=payload.actor_context,
            )
            try:
                return run_reports(
                    session,
                    active_data_root,
                    payload,
                    synthetic_artifact_marker=runtime_identity.synthetic_artifact_marker,
                )
            except ReportingError as exc:
                raise reporting_http_error(exc) from exc

    def dashboard_http_error(exc: DashboardError) -> HTTPException:
        return HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message})

    @app.get("/api/dashboard/summary")
    def get_dashboard_summary(month: Optional[str] = None) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return dashboard_summary(session, month=month)
            except DashboardError as exc:
                raise dashboard_http_error(exc) from exc

    @app.get("/api/dashboard/cashflow")
    def get_dashboard_cashflow(months: int = 6, month: Optional[str] = None) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return dashboard_cashflow(session, months=months, anchor_month=month)
            except DashboardError as exc:
                raise dashboard_http_error(exc) from exc

    @app.get("/api/dashboard/category-spend")
    def get_dashboard_category_spend(month: Optional[str] = None) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return dashboard_category_spend(session, month=month)
            except DashboardError as exc:
                raise dashboard_http_error(exc) from exc

    @app.get("/api/dashboard/pool-progress")
    def get_dashboard_pool_progress(month: Optional[str] = None) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return dashboard_pool_progress(session, month=month)
            except DashboardError as exc:
                raise dashboard_http_error(exc) from exc

    @app.get("/api/dashboard/net-worth")
    def get_dashboard_net_worth(
        date_from: Optional[str] = Query(default=None, alias="from"),
        date_to: Optional[str] = Query(default=None, alias="to"),
        include_estimates: bool = False,
    ) -> Dict[str, Any]:
        with create_session() as session:
            return dashboard_net_worth(
                session,
                date_from=date_from,
                date_to=date_to,
                include_estimates=include_estimates,
            )

    @app.get("/api/analyst-pack/options")
    def get_analyst_pack_options(month: Optional[str] = None) -> Dict[str, Any]:
        with create_session() as session:
            return analyst_pack_options(session, month=month)

    @app.get("/api/analyst-pack/prompts")
    def get_analyst_pack_prompts() -> Dict[str, Any]:
        return list_analyst_pack_prompts()

    @app.post("/api/analyst-pack/build")
    def post_analyst_pack_build(payload: AnalystExportRequest) -> Dict[str, Any]:
        active_data_root = get_data_root()
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.EXPORTS_CREATE,
                DataScopeKey.ADVISOR_EXPORT_ARTIFACTS,
                actor_context=payload.actor_context,
            )
            try:
                return build_analyst_pack(
                    session,
                    active_data_root,
                    payload,
                    synthetic_artifact_marker=runtime_identity.synthetic_artifact_marker,
                )
            except ReportingError as exc:
                raise reporting_http_error(exc) from exc

    @app.post("/api/monthly-close/draft")
    def post_monthly_close_draft(payload: MonthlyCloseRequest) -> Dict[str, Any]:
        active_data_root = get_data_root()
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.MONTHLY_CLOSE_RUN,
                DataScopeKey.MONTHLY_CLOSE,
                actor_context=payload.actor_context,
            )
            try:
                return create_monthly_close(
                    session,
                    active_data_root,
                    payload,
                    status="draft",
                    synthetic_artifact_marker=runtime_identity.synthetic_artifact_marker,
                )
            except ReportingError as exc:
                raise reporting_http_error(exc) from exc

    @app.post("/api/monthly-close/finalize")
    def post_monthly_close_finalize(payload: MonthlyCloseRequest) -> Dict[str, Any]:
        active_data_root = get_data_root()
        registry = get_elevated_mode_registry()
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.MONTHLY_CLOSE_RUN,
                DataScopeKey.MONTHLY_CLOSE,
                actor_context=payload.actor_context,
            )
            elevated_session = registry.get_active(session, current_elevated_session_id())
            try:
                return create_monthly_close(
                    session,
                    active_data_root,
                    payload,
                    status="final",
                    synthetic_artifact_marker=runtime_identity.synthetic_artifact_marker,
                    elevated_session=elevated_session,
                )
            except ReportingError as exc:
                raise reporting_http_error(exc) from exc

    @app.post("/api/exports/advisor")
    def post_advisor_export(payload: AdvisorExportRequest) -> Dict[str, Any]:
        active_data_root = get_data_root()
        with create_session() as session:
            require_permission(
                session,
                payload.actor,
                ActionKey.EXPORTS_CREATE,
                DataScopeKey.ADVISOR_EXPORT_ARTIFACTS,
                actor_context=payload.actor_context,
            )
            try:
                return create_advisor_export(
                    session,
                    active_data_root,
                    payload,
                    synthetic_artifact_marker=runtime_identity.synthetic_artifact_marker,
                )
            except ReportingError as exc:
                raise reporting_http_error(exc) from exc

    @app.get("/api/artifacts")
    def get_artifacts() -> Dict[str, Any]:
        with create_session() as session:
            return {"artifacts": list_artifacts(session)}

    @app.get("/api/artifacts/{artifact_id}/download")
    def download_artifact(artifact_id: str) -> FileResponse:
        active_data_root = get_data_root()
        with create_session() as session:
            try:
                return FileResponse(artifact_download_path(session, active_data_root, artifact_id))
            except ReportingError as exc:
                raise reporting_http_error(exc) from exc

    if STATIC_DIR.exists():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

        @app.get("/{full_path:path}")
        def serve_ui(full_path: str) -> FileResponse:
            static_root = STATIC_DIR.resolve()
            requested = (STATIC_DIR / full_path).resolve()
            if full_path and requested.is_relative_to(static_root) and requested.is_file():
                return FileResponse(requested)
            return FileResponse(STATIC_DIR / "index.html", headers=UI_SHELL_CACHE_HEADERS)

    return app


app = create_app()

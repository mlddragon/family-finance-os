from contextlib import asynccontextmanager
from pathlib import Path
import os
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from dillon_finances import __version__
from dillon_finances.database import create_sqlite_engine, upgrade_database
from dillon_finances.decision_events import (
    DecisionEventError,
    DecisionEventRequest,
    create_decision_event,
)
from dillon_finances.import_validation import (
    ImportValidationError,
    accept_import_batch,
    list_validation_findings,
    save_upload,
    scan_inbox,
    serialize_import_batch,
    validate_import_batch,
)
from dillon_finances.ledger_normalization import get_transaction, list_transactions
from dillon_finances.operator_summary import operator_summary_payload
from dillon_finances.reporting import (
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
from dillon_finances.runtime import bootstrap_data_root
from dillon_finances.settings_service import (
    SettingsPatchRequest,
    SettingsValidationError,
    apply_settings_patch,
    seed_default_settings,
    serialize_events,
    settings_payload,
)


APP_NAME = "Dillon Finances"
STATIC_DIR = Path(__file__).resolve().parent / "static"


class AcceptImportBatchRequest(BaseModel):
    acknowledge_warnings: bool = False


def _default_data_root() -> Path:
    return Path(os.environ.get("DATA_ROOT", "/data")).expanduser().resolve()


def _database_status(data_root: Path) -> Dict[str, str]:
    database_path = data_root / "database" / "dillon_finances.sqlite3"
    if database_path.exists():
        return {"status": "present", "path": str(database_path)}
    return {"status": "not_initialized", "path": str(database_path)}


def create_app(
    *,
    data_root: Optional[Path] = None,
    local_bind_host: Optional[str] = None,
) -> FastAPI:
    configured_data_root = data_root or _default_data_root()
    resolved_data_root: Optional[Path] = None
    engine: Optional[Engine] = None
    bind_host = local_bind_host or os.environ.get("APP_BIND_HOST", "127.0.0.1")

    def get_data_root() -> Path:
        nonlocal resolved_data_root
        if resolved_data_root is None:
            resolved_data_root = bootstrap_data_root(configured_data_root)
        return resolved_data_root

    def get_database_path() -> Path:
        return get_data_root() / "database" / "dillon_finances.sqlite3"

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

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        initialize_runtime_state()
        yield

    app = FastAPI(title=APP_NAME, version=__version__, lifespan=lifespan)

    def status_payload() -> Dict[str, Any]:
        active_data_root = get_data_root()
        return {
            "app": APP_NAME,
            "version": __version__,
            "local_only": bind_host == "127.0.0.1",
            "bind_host": bind_host,
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

    @app.get("/api/operator-summary")
    def operator_summary() -> Dict[str, Any]:
        with create_session() as session:
            return operator_summary_payload(session, runtime=status_payload())

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
    async def upload_source_file(file: UploadFile = File(...)) -> Dict[str, Any]:
        active_data_root = get_data_root()
        filename = file.filename or "uploaded-file"
        content = await file.read()
        with create_session() as session:
            try:
                batch = save_upload(session, active_data_root, filename, content)
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
            try:
                return accept_import_batch(
                    session,
                    active_data_root,
                    batch_id,
                    acknowledge_warnings=request_payload.acknowledge_warnings,
                )
            except ImportValidationError as exc:
                raise import_validation_http_error(exc) from exc

    @app.get("/api/validation-findings")
    def get_validation_findings() -> Dict[str, Any]:
        with create_session() as session:
            return {"findings": list_validation_findings(session)}

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

    @app.post("/api/decision-events")
    def post_decision_event(payload: DecisionEventRequest) -> Dict[str, Any]:
        with create_session() as session:
            try:
                return create_decision_event(session, payload)
            except DecisionEventError as exc:
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
            )

    @app.patch("/api/settings")
    def patch_settings(payload: SettingsPatchRequest) -> Dict[str, Any]:
        active_data_root = get_data_root()
        with create_session() as session:
            try:
                events = apply_settings_patch(session, payload)
                return {
                    **settings_payload(
                        session,
                        data_root=active_data_root,
                        local_only=bind_host == "127.0.0.1",
                    ),
                    "events": serialize_events(events),
                }
            except SettingsValidationError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=[{"code": exc.code, "message": exc.message}],
                ) from exc

    def reporting_http_error(exc: ReportingError) -> HTTPException:
        return HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, **exc.detail},
        )

    @app.post("/api/reports/run")
    def post_reports_run(payload: ReportRunRequest) -> Dict[str, Any]:
        active_data_root = get_data_root()
        with create_session() as session:
            try:
                return run_reports(session, active_data_root, payload)
            except ReportingError as exc:
                raise reporting_http_error(exc) from exc

    @app.post("/api/monthly-close/draft")
    def post_monthly_close_draft(payload: MonthlyCloseRequest) -> Dict[str, Any]:
        active_data_root = get_data_root()
        with create_session() as session:
            try:
                return create_monthly_close(session, active_data_root, payload, status="draft")
            except ReportingError as exc:
                raise reporting_http_error(exc) from exc

    @app.post("/api/monthly-close/finalize")
    def post_monthly_close_finalize(payload: MonthlyCloseRequest) -> Dict[str, Any]:
        active_data_root = get_data_root()
        with create_session() as session:
            try:
                return create_monthly_close(session, active_data_root, payload, status="final")
            except ReportingError as exc:
                raise reporting_http_error(exc) from exc

    @app.post("/api/exports/advisor")
    def post_advisor_export(payload: AdvisorExportRequest) -> Dict[str, Any]:
        active_data_root = get_data_root()
        with create_session() as session:
            try:
                return create_advisor_export(session, active_data_root, payload)
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
            requested = STATIC_DIR / full_path
            if full_path and requested.is_file():
                return FileResponse(requested)
            return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()

from contextlib import asynccontextmanager
from pathlib import Path
import os
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from dillon_finances import __version__
from dillon_finances.database import create_sqlite_engine, upgrade_database
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

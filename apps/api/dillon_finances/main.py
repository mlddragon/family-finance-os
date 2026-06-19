from contextlib import asynccontextmanager
from pathlib import Path
import os
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from dillon_finances import __version__
from dillon_finances.runtime import bootstrap_data_root


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
    bind_host = local_bind_host or os.environ.get("APP_BIND_HOST", "127.0.0.1")

    def get_data_root() -> Path:
        nonlocal resolved_data_root
        if resolved_data_root is None:
            resolved_data_root = bootstrap_data_root(configured_data_root)
        return resolved_data_root

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        get_data_root()
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

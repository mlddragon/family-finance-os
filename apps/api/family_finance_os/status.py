from __future__ import annotations

from pathlib import Path
from typing import Any

from family_finance_os import __version__
from family_finance_os.database import resolve_database_path
from family_finance_os.runtime import RuntimeEnvironment


APP_NAME = "Family Finance OS"


def database_status(data_root: Path) -> dict[str, str]:
    database_path = resolve_database_path(data_root / "database")
    if database_path.exists():
        return {"status": "present", "path": str(database_path)}
    return {"status": "not_initialized", "path": str(database_path)}


def status_payload(
    *,
    data_root: Path,
    bind_host: str,
    runtime_environment: RuntimeEnvironment,
) -> dict[str, Any]:
    return {
        "app": APP_NAME,
        "version": __version__,
        "local_only": bind_host == "127.0.0.1",
        "bind_host": bind_host,
        **runtime_environment.to_status_fields(),
        "data_root": {
            "path": str(data_root),
            "exists": data_root.exists(),
        },
        "database": database_status(data_root),
    }

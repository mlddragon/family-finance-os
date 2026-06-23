from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

PRIMARY_DATABASE_FILENAME = "family_finance_os.sqlite3"
LEGACY_DATABASE_FILENAME = "dillon_finances.sqlite3"


class DatabaseConfigurationError(RuntimeError):
    pass


def resolve_database_path(database_dir: Path) -> Path:
    primary_path = database_dir / PRIMARY_DATABASE_FILENAME
    legacy_path = database_dir / LEGACY_DATABASE_FILENAME
    if primary_path.exists():
        return primary_path
    if legacy_path.exists():
        return legacy_path
    return primary_path


def _ensure_safe_database_path(database_path: Path) -> Path:
    expanded_path = database_path.expanduser()
    parent = expanded_path.parent
    if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
        raise DatabaseConfigurationError("SQLite database parent must be a safe directory.")
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DatabaseConfigurationError("SQLite database parent must be a safe directory.") from exc
    if parent.is_symlink() or not parent.is_dir():
        raise DatabaseConfigurationError("SQLite database parent must be a safe directory.")
    if expanded_path.is_symlink() or (expanded_path.exists() and not expanded_path.is_file()):
        raise DatabaseConfigurationError("SQLite database file must be a safe regular file.")
    return expanded_path.resolve()


def sqlite_url(database_path: Path) -> str:
    return f"sqlite:///{database_path.expanduser().resolve()}"


def create_sqlite_engine(database_path: Path) -> Engine:
    resolved_database_path = _ensure_safe_database_path(database_path)
    engine = create_engine(
        sqlite_url(resolved_database_path),
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def alembic_config(database_path: Path) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", sqlite_url(database_path))
    return config


def upgrade_database(database_path: Path) -> None:
    resolved_database_path = _ensure_safe_database_path(database_path)
    command.upgrade(alembic_config(resolved_database_path), "head")

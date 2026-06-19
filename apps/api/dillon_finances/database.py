from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def sqlite_url(database_path: Path) -> str:
    return f"sqlite:///{database_path.expanduser().resolve()}"


def create_sqlite_engine(database_path: Path) -> Engine:
    database_path.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        sqlite_url(database_path),
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
    database_path.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(alembic_config(database_path), "head")

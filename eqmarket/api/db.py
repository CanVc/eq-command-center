from __future__ import annotations

import os
import sqlite3
from pathlib import Path


DB_PATH_ENV = "EQMARKET_DB_PATH"
DEFAULT_DB_PATH = Path("data/eqmarket.sqlite")


def resolve_db_path(db_path: str | Path | None = None) -> Path:
    configured_path = Path(db_path) if db_path is not None else Path(os.environ.get(DB_PATH_ENV, DEFAULT_DB_PATH))
    return configured_path.expanduser().resolve()


def sqlite_readonly_uri(db_path: str | Path) -> str:
    return f"{resolve_db_path(db_path).as_uri()}?mode=ro"


def connect_readonly(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(sqlite_readonly_uri(db_path), uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA query_only = ON")
    return connection

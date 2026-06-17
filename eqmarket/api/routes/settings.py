from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from eqmarket.api.db import connect_readonly
from eqmarket.local_settings import (
    LogPathPickerUnavailable,
    choose_eq_log_path,
    get_configured_log_path,
    set_configured_log_path,
)


DEFAULT_SERVER = "frostreaver"

router = APIRouter()


class LogPathUpdate(BaseModel):
    log_path: str | None = None


@router.get("/api/settings/status")
def settings_status(
    request: Request,
    server: str = Query(DEFAULT_SERVER, min_length=1),
) -> dict[str, Any]:
    active_server = _normalize_server(server)
    latest_import, import_runs_error = _fetch_latest_tlp_import(request.app.state.db_path)

    return {
        "status": "ok",
        "db_path": str(request.app.state.db_path),
        "default_server": DEFAULT_SERVER,
        "active_server": active_server,
        "latest_tlp_import": latest_import,
        "import_runs_error": import_runs_error,
        **_fetch_log_settings(request.app.state.db_path, active_server),
    }


@router.put("/api/settings/log-path")
def update_log_path(
    payload: LogPathUpdate,
    request: Request,
    server: str = Query(DEFAULT_SERVER, min_length=1),
) -> dict[str, Any]:
    active_server = _normalize_server(server)
    _save_log_path(request.app.state.db_path, payload.log_path)
    return _fetch_log_settings(request.app.state.db_path, active_server)


@router.post("/api/settings/log-path/browse")
async def browse_log_path(
    request: Request,
    server: str = Query(DEFAULT_SERVER, min_length=1),
) -> dict[str, Any]:
    active_server = _normalize_server(server)
    current_path = get_configured_log_path(request.app.state.db_path)

    try:
        selected_path = choose_eq_log_path(current_path)
    except LogPathPickerUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if selected_path:
        _save_log_path(request.app.state.db_path, selected_path)

    return _fetch_log_settings(request.app.state.db_path, active_server)


def _save_log_path(db_path: str | Path, log_path: str | None) -> None:
    try:
        set_configured_log_path(db_path, log_path)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _normalize_server(server: str) -> str:
    normalized = server.strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="server must not be blank")
    return normalized


def _fetch_log_settings(db_path: str | Path, server: str) -> dict[str, Any]:
    log_path = get_configured_log_path(db_path)
    log_exists = Path(log_path).exists() if log_path else None
    log_import_state, log_settings_error = _fetch_log_import_state(db_path, server, log_path)

    return {
        "eq_log_path": log_path,
        "eq_log_exists": log_exists,
        "eq_log_import_state": log_import_state,
        "log_settings_error": log_settings_error,
    }


def _fetch_log_import_state(
    db_path: str | Path,
    server: str,
    log_path: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with closing(connect_readonly(db_path)) as connection:
            if log_path:
                row = connection.execute(
                    """
                    SELECT log_path, server, file_size, file_mtime, last_position, updated_at
                    FROM log_import_state
                    WHERE log_path = ? AND lower(server) = lower(?)
                    """,
                    (log_path, server),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT log_path, server, file_size, file_mtime, last_position, updated_at
                    FROM log_import_state
                    WHERE lower(server) = lower(?)
                    ORDER BY datetime(updated_at) DESC, log_path DESC
                    LIMIT 1
                    """,
                    (server,),
                ).fetchone()
    except sqlite3.Error as exc:
        return None, str(exc)

    if row is None:
        return None, None

    return {
        "log_path": row["log_path"],
        "server": row["server"],
        "file_size": row["file_size"],
        "file_mtime": row["file_mtime"],
        "last_position": int(row["last_position"]),
        "updated_at": row["updated_at"],
    }, None


def _fetch_latest_tlp_import(db_path: str | Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with closing(connect_readonly(db_path)) as connection:
            row = connection.execute(
                """
                SELECT
                    import_run_id,
                    source_name,
                    source_url,
                    status,
                    items_seen,
                    items_inserted,
                    items_updated,
                    error,
                    started_at,
                    finished_at
                FROM import_runs
                WHERE source_name LIKE 'tlp_auctions_%'
                ORDER BY datetime(COALESCE(finished_at, started_at)) DESC, import_run_id DESC
                LIMIT 1
                """
            ).fetchone()
    except sqlite3.Error as exc:
        return None, str(exc)

    if row is None:
        return None, None

    return {
        "import_run_id": int(row["import_run_id"]),
        "source_name": row["source_name"],
        "source_url": row["source_url"],
        "status": row["status"],
        "items_seen": int(row["items_seen"]),
        "items_inserted": int(row["items_inserted"]),
        "items_updated": int(row["items_updated"]),
        "error": row["error"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }, None

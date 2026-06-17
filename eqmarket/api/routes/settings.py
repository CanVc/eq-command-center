from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from eqmarket.api.db import connect_readonly


DEFAULT_SERVER = "frostreaver"

router = APIRouter()


@router.get("/api/settings/status")
def settings_status(
    request: Request,
    server: str = Query(DEFAULT_SERVER, min_length=1),
) -> dict[str, Any]:
    latest_import, import_runs_error = _fetch_latest_tlp_import(request.app.state.db_path)

    return {
        "status": "ok",
        "db_path": str(request.app.state.db_path),
        "default_server": DEFAULT_SERVER,
        "active_server": _normalize_server(server),
        "latest_tlp_import": latest_import,
        "import_runs_error": import_runs_error,
    }


def _normalize_server(server: str) -> str:
    normalized = server.strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="server must not be blank")
    return normalized


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

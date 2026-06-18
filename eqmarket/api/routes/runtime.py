from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from eqmarket.api.db import connect_readonly
from eqmarket.price_importer import count_stale_listing_item_ids
from eqmarket.sources.tlp_auctions import TlpAuctionsError, db_server_name


DEFAULT_SERVER = "frostreaver"
DEFAULT_STALE_PRICE_HOURS = 6.0

router = APIRouter()


@router.get("/api/runtime/status")
def runtime_status(
    request: Request,
    server: str = Query(DEFAULT_SERVER, min_length=1),
    max_age_hours: float | None = Query(None, ge=0, le=24 * 30),
    max_age_minutes: float | None = Query(None, ge=0, le=24 * 30 * 60),
) -> dict[str, Any]:
    db_server = _normalize_server(server)
    db_path = Path(request.app.state.db_path)
    effective_max_age_hours = _resolve_max_age_hours(max_age_hours, max_age_minutes)

    return {
        "server": db_server,
        "max_age_hours": effective_max_age_hours,
        "max_age_minutes": round(effective_max_age_hours * 60, 2),
        "stale_item_count": _count_stale_items_or_503(db_path, db_server, effective_max_age_hours),
        "latest_log_sale_at": _fetch_latest_log_sale_at(db_path, db_server),
        "log_watcher": _log_watcher_status(request),
    }


def _normalize_server(server: str) -> str:
    try:
        return db_server_name(server)
    except TlpAuctionsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _resolve_max_age_hours(max_age_hours: float | None, max_age_minutes: float | None) -> float:
    if max_age_minutes is not None:
        return max_age_minutes / 60
    if max_age_hours is not None:
        return max_age_hours
    return DEFAULT_STALE_PRICE_HOURS


def _count_stale_items_or_503(db_path: Path, db_server: str, max_age_hours: float) -> int:
    try:
        return count_stale_listing_item_ids(db_path, db_server, max_age_hours=max_age_hours)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"SQLite stale item count failed: {exc}") from exc


def _fetch_latest_log_sale_at(db_path: Path, db_server: str) -> str | None:
    try:
        with closing(connect_readonly(db_path)) as connection:
            row = connection.execute(
                """
                SELECT max(timestamp)
                FROM market_listings
                WHERE lower(server) = lower(?)
                  AND source = 'eq_log'
                """,
                (db_server,),
            ).fetchone()
    except sqlite3.Error:
        return None
    return str(row[0]) if row and row[0] else None


def _log_watcher_status(request: Request) -> dict[str, Any] | None:
    watcher = getattr(request.app.state, "log_watcher", None)
    if watcher is None:
        return None
    return watcher.status()

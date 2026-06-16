from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from eqmarket.api.db import connect_readonly


DEFAULT_LIMIT = 100


router = APIRouter()


@router.get("/api/listings/recent")
def recent_listings(
    request: Request,
    server: str = Query("frostreaver", min_length=1),
    q: str | None = Query(None),
    limit: int = Query(DEFAULT_LIMIT, gt=0, le=500),
    offset: int = Query(0, ge=0),
) -> list[dict[str, Any]]:
    db_server = _normalize_server(server)
    search_text = _normalize_search(q)

    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        return _fetch_recent_listings(
            connection,
            db_server,
            search_text=search_text,
            limit=limit,
            offset=offset,
        )


def _fetch_recent_listings(
    connection: sqlite3.Connection,
    db_server: str,
    *,
    search_text: str | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    search_filter = ""
    params: list[Any] = [db_server]

    if search_text is not None:
        search_filter = """
          AND (
                lower(ml.item_name) LIKE ? ESCAPE '\\'
                OR lower(COALESCE(i.name, '')) LIKE ? ESCAPE '\\'
                OR lower(COALESCE(ml.seller, '')) LIKE ? ESCAPE '\\'
              )
        """
        search_pattern = _like_pattern(search_text)
        params.extend([search_pattern, search_pattern, search_pattern])

    params.extend([limit, offset])

    rows = connection.execute(
        f"""
        SELECT
            ml.listing_id,
            ml.timestamp,
            ml.seller,
            ml.item_id,
            COALESCE(i.name, ml.item_name) AS item_name,
            ml.price_raw,
            ml.price_pp,
            ml.source,
            ml.confidence
        FROM market_listings ml
        LEFT JOIN items i
            ON i.item_id = ml.item_id
        WHERE lower(ml.server) = ?
{search_filter}
        ORDER BY datetime(ml.timestamp) DESC, ml.timestamp DESC, ml.listing_id DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()

    return [_listing_payload(row) for row in rows]


def _listing_payload(row: sqlite3.Row) -> dict[str, Any]:
    item_id = _optional_int(row["item_id"])

    return {
        "listing_id": int(row["listing_id"]),
        "timestamp": row["timestamp"],
        "seller": row["seller"],
        "item": {
            "item_id": item_id,
            "name": row["item_name"],
        },
        "item_id": item_id,
        "item_name": row["item_name"],
        "price_raw": row["price_raw"],
        "price_pp": _optional_int(row["price_pp"]),
        "source": row["source"],
        "confidence": row["confidence"],
        "resolved": item_id is not None,
    }


def _normalize_server(server: str) -> str:
    db_server = server.strip().lower()
    if not db_server:
        raise HTTPException(status_code=400, detail="server must not be blank")
    return db_server


def _normalize_search(q: str | None) -> str | None:
    if q is None:
        return None

    search_text = q.strip().lower()
    return search_text or None


def _like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _connect_or_503(db_path: str | Path) -> sqlite3.Connection:
    try:
        return connect_readonly(db_path)
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"SQLite database is not readable: {exc}") from exc


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)

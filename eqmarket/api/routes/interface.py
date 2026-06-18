from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from eqmarket.api.db import connect_readonly
from eqmarket.price_importer import mark_tlp_prices_stale
from eqmarket.sources.tlp_auctions import TlpAuctionsError, db_server_name


DEFAULT_SERVER = "frostreaver"
DEFAULT_STALE_PRICE_MINUTES = 6 * 60

LISTING_ITEM_PREFERENCE_EXPRESSION = """
COALESCE(
    (
        SELECT ip.status
        FROM item_preferences ip
        WHERE ip.server = lower(ml.server)
          AND ip.preference_key_kind = 'item_id'
          AND ip.preference_key = CAST(ml.item_id AS TEXT)
    ),
    (
        SELECT ip.status
        FROM item_preferences ip
        WHERE ip.server = lower(ml.server)
          AND ip.preference_key_kind = 'name'
          AND ip.preference_key = i.normalized_name
    ),
    (
        SELECT ip.status
        FROM item_preferences ip
        WHERE ip.server = lower(ml.server)
          AND ip.preference_key_kind = 'name'
          AND ip.preference_key = ml.normalized_item_name
    )
)
"""

router = APIRouter()


@router.get("/api/interface/tlp-errors")
def tlp_errors(
    request: Request,
    server: str = Query(DEFAULT_SERVER, min_length=1),
    max_age_minutes: float = Query(DEFAULT_STALE_PRICE_MINUTES, ge=0, le=24 * 30 * 60),
) -> dict[str, Any]:
    db_server = _normalize_server(server)
    max_age_hours = max_age_minutes / 60

    try:
        with closing(connect_readonly(request.app.state.db_path)) as connection:
            stale_items = _fetch_stale_tlp_items(connection, db_server, max_age_hours=max_age_hours)
            latest_import = _fetch_latest_tlp_import(connection)
            errors = _fetch_active_tlp_errors(connection, db_server, stale_items)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"SQLite TLP interface status failed: {exc}") from exc

    return {
        "server": db_server,
        "max_age_minutes": max_age_minutes,
        "max_age_hours": max_age_hours,
        "stale_item_count": len(stale_items),
        "latest_tlp_import": latest_import,
        "active_errors": errors,
        "active_error_count": len(errors),
    }


@router.post("/api/interface/tlp-prices/mark-stale")
def mark_tlp_stale(
    request: Request,
    server: str = Query(DEFAULT_SERVER, min_length=1),
) -> dict[str, Any]:
    db_server = _normalize_server(server)

    try:
        affected_count = mark_tlp_prices_stale(Path(request.app.state.db_path), db_server)
    except TlpAuctionsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"SQLite TLP stale invalidation failed: {exc}") from exc

    return {
        "server": db_server,
        "affected_count": affected_count,
    }


@router.get("/api/interface/log-parse-issues")
def log_parse_issues(
    request: Request,
    server: str = Query(DEFAULT_SERVER, min_length=1),
    limit: int = Query(500, ge=1, le=5000),
) -> dict[str, Any]:
    db_server = _normalize_server(server)

    try:
        with closing(connect_readonly(request.app.state.db_path)) as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    server,
                    log_path,
                    timestamp,
                    timestamp_raw,
                    seller,
                    raw_line,
                    reason_code,
                    reason,
                    created_at,
                    last_seen_at,
                    seen_count
                FROM log_parse_issues
                WHERE lower(server) = lower(?)
                ORDER BY datetime(last_seen_at) DESC, id DESC
                LIMIT ?
                """,
                (db_server, limit),
            ).fetchall()
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"SQLite log parse issues failed: {exc}") from exc

    issues = [_log_parse_issue_payload(row) for row in rows]
    return {
        "server": db_server,
        "issues": issues,
        "issue_count": len(issues),
        "limit": limit,
    }


def _normalize_server(server: str) -> str:
    try:
        return db_server_name(server)
    except TlpAuctionsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _fetch_stale_tlp_items(
    connection: sqlite3.Connection,
    server: str,
    *,
    max_age_hours: float,
) -> dict[int, dict[str, Any]]:
    rows = connection.execute(
        f"""
        SELECT
            ml.item_id,
            COALESCE(i.name, max(ml.item_name)) AS item_name,
            mp.confidence AS price_confidence,
            mp.source AS price_source,
            mp.last_refresh_at AS last_refresh_at,
            mp.raw_payload AS price_raw_payload,
            max(ml.timestamp) AS latest_listing_at
        FROM market_listings ml
        LEFT JOIN items i
            ON i.item_id = ml.item_id
        LEFT JOIN market_prices mp
            ON mp.item_id = ml.item_id AND lower(mp.server) = lower(ml.server)
        WHERE lower(ml.server) = lower(?)
          AND ml.item_id IS NOT NULL
          AND ml.price_pp IS NOT NULL
          AND COALESCE({LISTING_ITEM_PREFERENCE_EXPRESSION}, 'neutral') != 'ignored'
          AND (
                mp.item_id IS NULL
                OR mp.confidence = 'failed'
                OR mp.source = 'tlp_auctions_history_failed'
                OR mp.last_refresh_at IS NULL
                OR datetime(mp.last_refresh_at) <= datetime('now', ?)
              )
        GROUP BY ml.item_id
        """,
        (server, f"-{max_age_hours:g} hours"),
    ).fetchall()

    return {
        int(row["item_id"]): {
            "item_id": int(row["item_id"]),
            "item_name": row["item_name"],
            "price_confidence": row["price_confidence"],
            "price_source": row["price_source"],
            "last_refresh_at": row["last_refresh_at"],
            "price_raw_payload": row["price_raw_payload"],
            "latest_listing_at": row["latest_listing_at"],
        }
        for row in rows
    }


def _fetch_active_tlp_errors(
    connection: sqlite3.Connection,
    server: str,
    stale_items: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    if not stale_items:
        return []

    rows = connection.execute(
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
        WHERE source_name = 'tlp_auctions_history'
          AND status = 'failed'
          AND lower(COALESCE(source_url, '')) LIKE ?
        ORDER BY datetime(COALESCE(finished_at, started_at)) DESC, import_run_id DESC
        """,
        (f"%server={server.lower()}%",),
    ).fetchall()

    errors: list[dict[str, Any]] = []
    represented_item_ids: set[int] = set()
    for row in rows:
        item_id = _item_id_from_source_url(row["source_url"])
        if item_id is None or item_id not in stale_items:
            continue
        if _is_no_data_price_marker(stale_items[item_id]):
            continue
        represented_item_ids.add(item_id)
        errors.append(
            {
                **_import_run_payload(row),
                **_stale_item_error_payload(stale_items[item_id]),
                "active": True,
                "origin": "import_run",
            }
        )

    for item_id, item in stale_items.items():
        if item_id in represented_item_ids:
            continue
        if _is_no_data_price_marker(item):
            continue
        if item["price_confidence"] != "failed" and item["price_source"] != "tlp_auctions_history_failed":
            continue
        marker_error = _error_from_price_raw_payload(item.get("price_raw_payload"))
        errors.append(
            {
                "import_run_id": None,
                "source_name": item["price_source"] or "tlp_auctions_history_failed",
                "source_url": f"item_id={item_id};server={server}",
                "status": "failed",
                "items_seen": 0,
                "items_inserted": 0,
                "items_updated": 0,
                "error": marker_error or "Stored TLP refresh marker is failed.",
                "started_at": item["last_refresh_at"],
                "finished_at": item["last_refresh_at"],
                **_stale_item_error_payload(item),
                "active": True,
                "origin": "market_price_marker",
            }
        )

    return errors


def _fetch_latest_tlp_import(connection: sqlite3.Connection) -> dict[str, Any] | None:
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
    return _import_run_payload(row) if row is not None else None


def _is_no_data_price_marker(item: dict[str, Any]) -> bool:
    return item.get("price_confidence") == "no_data" or item.get("price_source") == "tlp_auctions_history_no_data"


def _stale_item_error_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "item_id": item["item_id"],
        "item_name": item["item_name"],
        "price_confidence": item["price_confidence"],
        "price_source": item["price_source"],
        "last_refresh_at": item["last_refresh_at"],
        "latest_listing_at": item["latest_listing_at"],
    }


def _item_id_from_source_url(source_url: str | None) -> int | None:
    if not source_url:
        return None

    for part in source_url.split(";"):
        key, separator, value = part.partition("=")
        if separator and key.strip().lower() == "item_id":
            try:
                return int(value)
            except ValueError:
                return None
    return None


def _error_from_price_raw_payload(raw_payload: str | None) -> str | None:
    if not raw_payload:
        return None
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return None
    error = payload.get("error")
    return str(error) if error else None


def _import_run_payload(row: sqlite3.Row) -> dict[str, Any]:
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
    }


def _log_parse_issue_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "server": row["server"],
        "log_path": row["log_path"],
        "timestamp": row["timestamp"],
        "timestamp_raw": row["timestamp_raw"],
        "seller": row["seller"],
        "raw_line": row["raw_line"],
        "reason_code": row["reason_code"],
        "reason": row["reason"],
        "created_at": row["created_at"],
        "last_seen_at": row["last_seen_at"],
        "seen_count": int(row["seen_count"]),
    }

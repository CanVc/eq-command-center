from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from eqmarket.api.db import connect_readonly


DEFAULT_RECENT_HOURS = 24
DEFAULT_TOP_LIMIT = 5
DEFAULT_MIN_DISCOUNT = 30.0


router = APIRouter()


@router.get("/api/dashboard/summary")
def dashboard_summary(
    request: Request,
    server: str = Query("frostreaver", min_length=1),
    recent_hours: int = Query(DEFAULT_RECENT_HOURS, gt=0, le=24 * 30),
    top_limit: int = Query(DEFAULT_TOP_LIMIT, gt=0, le=50),
    min_discount: float = Query(DEFAULT_MIN_DISCOUNT, ge=0, le=100),
) -> dict[str, Any]:
    db_server = _normalize_server(server)
    window_modifier = f"-{recent_hours} hours"

    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        listings_recent_count = _fetch_listing_count(connection, db_server, window_modifier)
        deals_recent_count = _fetch_deal_count(connection, db_server, window_modifier, min_discount)
        top_seen_items = _fetch_top_seen_items(connection, db_server, window_modifier, top_limit)
        top_discounts = _fetch_top_discounts(connection, db_server, window_modifier, min_discount, top_limit)
        krono_latest = _fetch_latest_krono(connection, db_server)

    return {
        "server": db_server,
        "recent_window_hours": recent_hours,
        "min_discount": min_discount,
        "listings_recent_count": listings_recent_count,
        "deals_recent_count": deals_recent_count,
        "krono_latest": krono_latest,
        "top_seen_items": top_seen_items,
        "top_discounts": top_discounts,
    }


@router.get("/api/krono/latest")
def krono_latest(
    request: Request,
    server: str = Query("frostreaver", min_length=1),
) -> dict[str, Any]:
    db_server = _normalize_server(server)

    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        krono = _fetch_latest_krono(connection, db_server)

    return krono


def _normalize_server(server: str) -> str:
    db_server = server.strip().lower()
    if not db_server:
        raise HTTPException(status_code=400, detail="server must not be blank")
    return db_server


def _connect_or_503(db_path: str | Path) -> sqlite3.Connection:
    try:
        return connect_readonly(db_path)
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"SQLite database is not readable: {exc}") from exc


def _fetch_listing_count(connection: sqlite3.Connection, db_server: str, window_modifier: str) -> int:
    row = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM market_listings
        WHERE lower(server) = ?
          AND datetime(timestamp) >= datetime('now', ?)
        """,
        (db_server, window_modifier),
    ).fetchone()
    return int(row["count"])


def _fetch_deal_count(
    connection: sqlite3.Connection,
    db_server: str,
    window_modifier: str,
    min_discount: float,
) -> int:
    row = connection.execute(
        """
        WITH priced_listings AS (
            SELECT
                ml.price_raw,
                ml.price_amount,
                ml.price_pp AS listing_price_pp,
                COALESCE(NULLIF(mp.median_pp, 0), NULLIF(mp.avg_pp, 0), NULLIF(mp.p25_pp, 0)) AS market_price_pp,
                mlr.status AS review_status
            FROM market_listings ml
            JOIN market_prices mp
                ON mp.item_id = ml.item_id AND lower(mp.server) = lower(ml.server)
            LEFT JOIN market_listing_reviews mlr
                ON mlr.listing_id = ml.listing_id
            WHERE lower(ml.server) = ?
              AND datetime(ml.timestamp) >= datetime('now', ?)
        )
        SELECT COUNT(*) AS count
        FROM priced_listings
        WHERE listing_price_pp > 0
          AND market_price_pp > 0
          AND COALESCE(review_status, 'active') = 'active'
          AND NOT (
                review_status IS NULL
                AND price_raw IS NOT NULL
                AND trim(price_raw) GLOB '[0-9]*'
                AND trim(price_raw) NOT GLOB '*[A-Za-z]*'
                AND price_amount IS NOT NULL
                AND listing_price_pp < market_price_pp * 0.05
                AND market_price_pp >= 10000
              )
          AND ((market_price_pp - listing_price_pp) * 100.0 / market_price_pp) >= ?
        """,
        (db_server, window_modifier, min_discount),
    ).fetchone()
    return int(row["count"])


def _fetch_top_seen_items(
    connection: sqlite3.Connection,
    db_server: str,
    window_modifier: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            MAX(ml.item_id) AS item_id,
            COALESCE(MAX(i.name), MIN(ml.item_name)) AS item_name,
            COUNT(*) AS seen_count,
            MAX(ml.timestamp) AS last_seen_at
        FROM market_listings ml
        LEFT JOIN items i
            ON i.item_id = ml.item_id
        WHERE lower(ml.server) = ?
          AND datetime(ml.timestamp) >= datetime('now', ?)
        GROUP BY
            CASE
                WHEN ml.item_id IS NOT NULL THEN 'item:' || ml.item_id
                ELSE 'name:' || COALESCE(ml.normalized_item_name, lower(ml.item_name))
            END
        ORDER BY seen_count DESC, last_seen_at DESC
        LIMIT ?
        """,
        (db_server, window_modifier, limit),
    ).fetchall()

    return [
        {
            "item_id": _optional_int(row["item_id"]),
            "item_name": row["item_name"],
            "seen_count": int(row["seen_count"]),
            "last_seen_at": row["last_seen_at"],
        }
        for row in rows
    ]


def _fetch_top_discounts(
    connection: sqlite3.Connection,
    db_server: str,
    window_modifier: str,
    min_discount: float,
    limit: int,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        WITH priced_listings AS (
            SELECT
                ml.listing_id,
                ml.timestamp,
                ml.seller,
                ml.item_id,
                COALESCE(i.name, ml.item_name) AS item_name,
                ml.price_raw,
                ml.price_amount,
                ml.price_pp AS listing_price_pp,
                ml.raw_line,
                COALESCE(NULLIF(mp.median_pp, 0), NULLIF(mp.avg_pp, 0), NULLIF(mp.p25_pp, 0)) AS market_price_pp,
                CASE
                    WHEN mp.median_pp IS NOT NULL AND mp.median_pp > 0 THEN 'median_pp'
                    WHEN mp.avg_pp IS NOT NULL AND mp.avg_pp > 0 THEN 'avg_pp'
                    WHEN mp.p25_pp IS NOT NULL AND mp.p25_pp > 0 THEN 'p25_pp'
                    ELSE NULL
                END AS market_price_source,
                mp.sample_size,
                mp.confidence,
                mlr.status AS review_status,
                ((COALESCE(NULLIF(mp.median_pp, 0), NULLIF(mp.avg_pp, 0), NULLIF(mp.p25_pp, 0)) - ml.price_pp) * 100.0
                    / COALESCE(NULLIF(mp.median_pp, 0), NULLIF(mp.avg_pp, 0), NULLIF(mp.p25_pp, 0))) AS discount_pct
            FROM market_listings ml
            JOIN market_prices mp
                ON mp.item_id = ml.item_id AND lower(mp.server) = lower(ml.server)
            LEFT JOIN items i
                ON i.item_id = ml.item_id
            LEFT JOIN market_listing_reviews mlr
                ON mlr.listing_id = ml.listing_id
            WHERE lower(ml.server) = ?
              AND datetime(ml.timestamp) >= datetime('now', ?)
              AND ml.price_pp > 0
              AND COALESCE(NULLIF(mp.median_pp, 0), NULLIF(mp.avg_pp, 0), NULLIF(mp.p25_pp, 0)) > 0
              AND COALESCE(mlr.status, 'active') = 'active'
              AND NOT (
                    mlr.status IS NULL
                    AND ml.price_raw IS NOT NULL
                    AND trim(ml.price_raw) GLOB '[0-9]*'
                    AND trim(ml.price_raw) NOT GLOB '*[A-Za-z]*'
                    AND ml.price_amount IS NOT NULL
                    AND ml.price_pp < COALESCE(NULLIF(mp.median_pp, 0), NULLIF(mp.avg_pp, 0), NULLIF(mp.p25_pp, 0)) * 0.05
                    AND COALESCE(NULLIF(mp.median_pp, 0), NULLIF(mp.avg_pp, 0), NULLIF(mp.p25_pp, 0)) >= 10000
                  )
        )
        SELECT *
        FROM priced_listings
        WHERE discount_pct >= ?
        ORDER BY discount_pct DESC, (market_price_pp - listing_price_pp) DESC, timestamp DESC, listing_id DESC
        LIMIT ?
        """,
        (db_server, window_modifier, min_discount, limit),
    ).fetchall()

    return [
        {
            "listing_id": int(row["listing_id"]),
            "timestamp": row["timestamp"],
            "seller": row["seller"],
            "item_id": _optional_int(row["item_id"]),
            "item_name": row["item_name"],
            "price_raw": row["price_raw"],
            "raw_line": row["raw_line"],
            "listing_price_pp": int(row["listing_price_pp"]),
            "market_price_pp": int(row["market_price_pp"]),
            "market_price_source": row["market_price_source"],
            "discount_pct": round(float(row["discount_pct"]), 2),
            "sample_size": _optional_int(row["sample_size"]),
            "confidence": row["confidence"],
        }
        for row in rows
    ]


def _fetch_latest_krono(connection: sqlite3.Connection, db_server: str) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT server, price_pp, source, confidence, last_refresh_at
        FROM krono_prices
        WHERE lower(server) = ?
        ORDER BY datetime(last_refresh_at) DESC
        LIMIT 1
        """,
        (db_server,),
    ).fetchone()

    if row is None:
        return {
            "server": db_server,
            "price_pp": None,
            "source": None,
            "confidence": None,
            "last_refresh_at": None,
        }

    return {
        "server": row["server"],
        "price_pp": int(row["price_pp"]),
        "source": row["source"],
        "confidence": row["confidence"],
        "last_refresh_at": row["last_refresh_at"],
    }


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)

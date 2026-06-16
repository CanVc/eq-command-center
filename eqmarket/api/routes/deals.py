from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from eqmarket.api.db import connect_readonly


DEFAULT_MIN_DISCOUNT = 30.0
DEFAULT_LIMIT = 100
LISTING_SCORE_PROFILE = "market_deals"


router = APIRouter()


@router.get("/api/deals")
def list_deals(
    request: Request,
    server: str = Query("frostreaver", min_length=1),
    min_discount: float = Query(DEFAULT_MIN_DISCOUNT, ge=0, le=100),
    limit: int = Query(DEFAULT_LIMIT, gt=0, le=500),
    min_price_pp: int = Query(0, ge=0),
    resolved_only: bool = Query(True),
) -> list[dict[str, Any]]:
    db_server = _normalize_server(server)

    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        return _fetch_deals(
            connection,
            db_server,
            min_discount=min_discount,
            min_price_pp=min_price_pp,
            resolved_only=resolved_only,
            limit=limit,
        )


def _fetch_deals(
    connection: sqlite3.Connection,
    db_server: str,
    *,
    min_discount: float,
    min_price_pp: int,
    resolved_only: bool,
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
                ml.price_pp AS listing_price_pp,
                COALESCE(NULLIF(mp.median_pp, 0), NULLIF(mp.avg_pp, 0), NULLIF(mp.p25_pp, 0)) AS market_price_pp,
                CASE
                    WHEN mp.median_pp IS NOT NULL AND mp.median_pp > 0 THEN 'median_pp'
                    WHEN mp.avg_pp IS NOT NULL AND mp.avg_pp > 0 THEN 'avg_pp'
                    WHEN mp.p25_pp IS NOT NULL AND mp.p25_pp > 0 THEN 'p25_pp'
                    ELSE NULL
                END AS market_price_source,
                mp.sample_size,
                mp.confidence,
                ls.deal_score AS stored_deal_score
            FROM market_listings ml
            JOIN market_prices mp
                ON mp.item_id = ml.item_id AND lower(mp.server) = lower(ml.server)
            LEFT JOIN items i
                ON i.item_id = ml.item_id
            LEFT JOIN listing_scores ls
                ON ls.listing_id = ml.listing_id AND ls.profile_name = ?
            WHERE lower(ml.server) = ?
              AND (? = 0 OR ml.item_id IS NOT NULL)
        )
        SELECT
            *,
            ((market_price_pp - listing_price_pp) * 100.0 / market_price_pp) AS discount_pct,
            (market_price_pp - listing_price_pp) AS potential_profit_pp
        FROM priced_listings
        WHERE listing_price_pp > 0
          AND market_price_pp > 0
          AND listing_price_pp >= ?
          AND ((market_price_pp - listing_price_pp) * 100.0 / market_price_pp) >= ?
        ORDER BY discount_pct DESC, potential_profit_pp DESC, timestamp DESC, listing_id DESC
        LIMIT ?
        """,
        (
            LISTING_SCORE_PROFILE,
            db_server,
            1 if resolved_only else 0,
            min_price_pp,
            min_discount,
            limit,
        ),
    ).fetchall()

    return [_deal_payload(row) for row in rows]


def _deal_payload(row: sqlite3.Row) -> dict[str, Any]:
    discount_pct = round(float(row["discount_pct"]), 2)
    stored_deal_score = _optional_float(row["stored_deal_score"])
    deal_score = stored_deal_score if stored_deal_score is not None else discount_pct

    return {
        "listing_id": int(row["listing_id"]),
        "timestamp": row["timestamp"],
        "seller": row["seller"],
        "item": {
            "item_id": _optional_int(row["item_id"]),
            "name": row["item_name"],
        },
        "item_id": _optional_int(row["item_id"]),
        "item_name": row["item_name"],
        "price_raw": row["price_raw"],
        "listing_price_pp": int(row["listing_price_pp"]),
        "market_price_pp": int(row["market_price_pp"]),
        "market_price_source": row["market_price_source"],
        "discount_pct": discount_pct,
        "potential_profit_pp": int(row["potential_profit_pp"]),
        "score": deal_score,
        "deal_score": deal_score,
        "sample_size": _optional_int(row["sample_size"]),
        "confidence": row["confidence"],
        "resolved": row["item_id"] is not None,
    }


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


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)

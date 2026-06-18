from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request

from eqmarket.api.db import connect_readonly


DEFAULT_MIN_DISCOUNT = 30.0
DEFAULT_LIMIT = 100
LISTING_SCORE_PROFILE = "market_deals"

DealSortBy = Literal["item", "seen_price", "market_price", "discount", "seller", "date", "score"]
DealSortDirection = Literal["asc", "desc"]


router = APIRouter()


@router.get("/api/deals")
def list_deals(
    request: Request,
    server: str = Query("frostreaver", min_length=1),
    min_discount: float = Query(DEFAULT_MIN_DISCOUNT, ge=0, le=100),
    limit: int = Query(DEFAULT_LIMIT, gt=0, le=500),
    min_price_pp: int = Query(0, ge=0),
    resolved_only: bool = Query(True),
    include_suspect: bool = Query(False),
    seller: str | None = Query(None),
    item: str | None = Query(None),
    date_from: str | None = Query(None),
    sort_by: DealSortBy = Query("discount"),
    sort_dir: DealSortDirection = Query("desc"),
) -> list[dict[str, Any]]:
    db_server = _normalize_server(server)
    seller_filter = _normalize_search(seller)
    item_filter = _normalize_search(item)
    normalized_date_from = _normalize_date_from(date_from)

    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        return _fetch_deals(
            connection,
            db_server,
            min_discount=min_discount,
            min_price_pp=min_price_pp,
            resolved_only=resolved_only,
            include_suspect=include_suspect,
            seller=seller_filter,
            item=item_filter,
            date_from=normalized_date_from,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
        )


def _fetch_deals(
    connection: sqlite3.Connection,
    db_server: str,
    *,
    min_discount: float,
    min_price_pp: int,
    resolved_only: bool,
    include_suspect: bool,
    limit: int,
    seller: str | None = None,
    item: str | None = None,
    date_from: str | None = None,
    sort_by: DealSortBy = "discount",
    sort_dir: DealSortDirection = "desc",
) -> list[dict[str, Any]]:
    base_filters: list[str] = []
    params: list[Any] = [LISTING_SCORE_PROFILE, db_server, 1 if resolved_only else 0]

    if seller is not None:
        base_filters.append("\n              AND lower(COALESCE(ml.seller, '')) LIKE ? ESCAPE '\\'")
        params.append(_like_pattern(seller))

    if item is not None:
        base_filters.append(
            """
              AND (
                    lower(ml.item_name) LIKE ? ESCAPE '\\'
                    OR lower(COALESCE(i.name, '')) LIKE ? ESCAPE '\\'
                  )"""
        )
        item_pattern = _like_pattern(item)
        params.extend([item_pattern, item_pattern])

    if date_from is not None:
        base_filters.append("\n              AND datetime(ml.timestamp) >= datetime(?)")
        params.append(date_from)

    params.extend([min_price_pp, 1 if include_suspect else 0, min_discount, limit])
    base_filter_sql = "".join(base_filters)
    order_by_sql = _deal_order_by_clause(sort_by, sort_dir)

    rows = connection.execute(
        f"""
        WITH priced_base AS (
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
                ls.deal_score AS stored_deal_score,
                mlr.status AS explicit_review_status,
                mlr.reason_code AS explicit_review_reason_code,
                mlr.note AS explicit_review_note,
                kp.price_pp AS krono_price_pp
            FROM market_listings ml
            JOIN market_prices mp
                ON mp.item_id = ml.item_id AND lower(mp.server) = lower(ml.server)
            LEFT JOIN items i
                ON i.item_id = ml.item_id
            LEFT JOIN listing_scores ls
                ON ls.listing_id = ml.listing_id AND ls.profile_name = ?
            LEFT JOIN market_listing_reviews mlr
                ON mlr.listing_id = ml.listing_id
            LEFT JOIN krono_prices kp
                ON lower(kp.server) = lower(ml.server)
            WHERE lower(ml.server) = ?
              AND (? = 0 OR ml.item_id IS NOT NULL){base_filter_sql}
        ),
        priced_listings AS (
            SELECT
                *,
                CASE
                    WHEN explicit_review_status IS NULL AND _is_auto_suspect = 1 THEN 'suspect'
                    ELSE COALESCE(explicit_review_status, 'active')
                END AS review_status,
                CASE
                    WHEN explicit_review_status IS NULL AND _is_likely_krono_missing_unit = 1 THEN 'likely_krono_price_missing_unit'
                    WHEN explicit_review_status IS NULL AND _is_auto_suspect = 1 THEN 'bare_price_extreme_discount'
                    ELSE explicit_review_reason_code
                END AS review_reason_code,
                explicit_review_note AS review_note
            FROM (
                SELECT
                    *,
                    CASE
                        WHEN price_raw IS NOT NULL
                          AND trim(price_raw) GLOB '[0-9]*'
                          AND trim(price_raw) NOT GLOB '*[A-Za-z]*'
                          AND price_amount IS NOT NULL
                          AND listing_price_pp > 0
                          AND market_price_pp >= 10000
                          AND listing_price_pp < market_price_pp * 0.05
                        THEN 1
                        ELSE 0
                    END AS _is_auto_suspect,
                    CASE
                        WHEN price_raw IS NOT NULL
                          AND trim(price_raw) GLOB '[0-9]*'
                          AND trim(price_raw) NOT GLOB '*[A-Za-z]*'
                          AND price_amount IS NOT NULL
                          AND listing_price_pp > 0
                          AND market_price_pp >= 10000
                          AND listing_price_pp < market_price_pp * 0.05
                          AND krono_price_pp IS NOT NULL
                          AND krono_price_pp > 0
                          AND ABS((price_amount * krono_price_pp) - market_price_pp) <= market_price_pp * 0.25
                        THEN 1
                        ELSE 0
                    END AS _is_likely_krono_missing_unit
                FROM priced_base
            ) reviewed_base
        )
        SELECT
            *,
            ((market_price_pp - listing_price_pp) * 100.0 / market_price_pp) AS discount_pct,
            (market_price_pp - listing_price_pp) AS potential_profit_pp,
            COALESCE(
                stored_deal_score,
                ((market_price_pp - listing_price_pp) * 100.0 / market_price_pp)
            ) AS score_sort
        FROM priced_listings
        WHERE listing_price_pp > 0
          AND market_price_pp > 0
          AND listing_price_pp >= ?
          AND review_status != 'discarded'
          AND (? = 1 OR review_status != 'suspect')
          AND ((market_price_pp - listing_price_pp) * 100.0 / market_price_pp) >= ?
        ORDER BY {order_by_sql}
        LIMIT ?
        """,
        params,
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
        "raw_line": row["raw_line"],
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
        "review_status": row["review_status"],
        "review_reason_code": row["review_reason_code"],
        "review_note": row["review_note"],
    }


def _normalize_server(server: str) -> str:
    db_server = server.strip().lower()
    if not db_server:
        raise HTTPException(status_code=400, detail="server must not be blank")
    return db_server


def _normalize_search(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip().lower()
    return normalized or None


def _normalize_date_from(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    try:
        if len(normalized) == 10:
            parsed_date = date.fromisoformat(normalized)
            return datetime.combine(parsed_date, time.min).strftime("%Y-%m-%d %H:%M:%S")

        parsed_datetime = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date_from must be an ISO date or datetime") from exc

    return parsed_datetime.isoformat(sep=" ", timespec="seconds")


def _like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _deal_order_by_clause(sort_by: DealSortBy, sort_dir: DealSortDirection) -> str:
    direction = "ASC" if sort_dir == "asc" else "DESC"

    if sort_by == "discount":
        return (
            f"discount_pct {direction}, potential_profit_pp {direction}, "
            f"datetime(timestamp) {direction}, timestamp {direction}, listing_id {direction}"
        )

    if sort_by == "date":
        return f"datetime(timestamp) {direction}, timestamp {direction}, listing_id {direction}"

    expression_by_sort: dict[DealSortBy, str] = {
        "item": "lower(COALESCE(item_name, ''))",
        "seen_price": "listing_price_pp",
        "market_price": "market_price_pp",
        "discount": "discount_pct",
        "seller": "lower(COALESCE(seller, ''))",
        "date": "datetime(timestamp)",
        "score": "score_sort",
    }
    expression = expression_by_sort[sort_by]
    return f"{expression} {direction}, discount_pct DESC, potential_profit_pp DESC, datetime(timestamp) DESC, listing_id DESC"


def _connect_or_503(db_path: str | Path) -> sqlite3.Connection:
    try:
        return connect_readonly(db_path)
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"SQLite database is not readable: {exc}") from exc


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)

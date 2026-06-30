from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from eqmarket.api.db import connect_readonly
from eqmarket.api.item_sources import fetch_item_sources_by_id
from eqmarket.db import init_db
from eqmarket.review_rules import (
    DiscardRule,
    SimilarRuleError,
    apply_discard_rule_to_matching_listings,
    create_or_update_discard_rule_for_listing,
    disable_discard_rules_for_signature,
    fetch_listing_ids_for_signature,
    fetch_listing_signature,
    restore_listing_ids,
)


DEFAULT_LIMIT = 100
DEFAULT_DISCARD_REASON = "manual"

ListingReviewStatus = Literal["active", "discarded", "suspect"]
ListingReviewStatusFilter = Literal["active", "discarded", "suspect", "all"]
ItemInterestFilter = Literal["tracked", "wanted", "ignored", "all"]

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


class ListingReviewUpdate(BaseModel):
    status: ListingReviewStatus
    reason_code: str | None = None
    note: str | None = None


class ListingReviewAction(BaseModel):
    reason_code: str | None = None
    note: str | None = None


router = APIRouter()


@router.put("/api/listings/{listing_id}/review")
def update_listing_review(
    listing_id: int,
    payload: ListingReviewUpdate,
    request: Request,
) -> dict[str, Any]:
    reason_code = _normalize_optional_text(payload.reason_code)
    note = _normalize_optional_text(payload.note)

    if payload.status in {"discarded", "suspect"} and reason_code is None:
        reason_code = DEFAULT_DISCARD_REASON

    with closing(_connect_writable_or_503(request.app.state.db_path)) as connection:
        review = _upsert_listing_review(
            connection,
            listing_id,
            status=payload.status,
            reason_code=reason_code,
            note=note,
        )
        connection.commit()

    return review


@router.post("/api/listings/{listing_id}/discard")
def discard_listing(
    listing_id: int,
    request: Request,
    payload: ListingReviewAction | None = None,
) -> dict[str, Any]:
    reason_code = _normalize_optional_text(payload.reason_code if payload is not None else None) or DEFAULT_DISCARD_REASON
    note = _normalize_optional_text(payload.note if payload is not None else None)

    with closing(_connect_writable_or_503(request.app.state.db_path)) as connection:
        review = _upsert_listing_review(
            connection,
            listing_id,
            status="discarded",
            reason_code=reason_code,
            note=note,
        )
        connection.commit()

    return review


@router.post("/api/listings/{listing_id}/discard-similar")
def discard_similar_listings(
    listing_id: int,
    request: Request,
    payload: ListingReviewAction | None = None,
) -> dict[str, Any]:
    reason_code = _normalize_optional_text(payload.reason_code if payload is not None else None) or DEFAULT_DISCARD_REASON
    note = _normalize_optional_text(payload.note if payload is not None else None)

    with closing(_connect_writable_or_503(request.app.state.db_path)) as connection:
        try:
            rule = create_or_update_discard_rule_for_listing(
                connection,
                listing_id,
                reason_code=reason_code,
                note=note,
            )
        except SimilarRuleError as exc:
            if str(exc) == "Listing not found":
                raise HTTPException(status_code=404, detail="Listing not found") from exc
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        matched_count = apply_discard_rule_to_matching_listings(
            connection,
            rule,
            override_active_reviews=True,
        )
        review = _fetch_listing_review_payload(connection, listing_id)
        connection.commit()

    return {
        "listing_id": listing_id,
        "server": rule.server,
        "action": "discard_similar",
        "rule": _discard_rule_payload(rule),
        "matched_count": matched_count,
        "review": review,
    }


@router.post("/api/listings/{listing_id}/restore")
def restore_listing(
    listing_id: int,
    request: Request,
) -> dict[str, Any]:
    with closing(_connect_writable_or_503(request.app.state.db_path)) as connection:
        review = _upsert_listing_review(
            connection,
            listing_id,
            status="active",
            reason_code=None,
            note=None,
        )
        connection.commit()

    return review


@router.post("/api/listings/{listing_id}/restore-similar")
def restore_similar_listings(
    listing_id: int,
    request: Request,
) -> dict[str, Any]:
    with closing(_connect_writable_or_503(request.app.state.db_path)) as connection:
        signature = fetch_listing_signature(connection, listing_id)
        if signature is None:
            raise HTTPException(status_code=404, detail="Listing not found")
        if signature.item_id is None:
            raise HTTPException(status_code=400, detail="Similar restore requires a resolved item_id")

        listing_ids = fetch_listing_ids_for_signature(connection, signature)
        disabled_rules = disable_discard_rules_for_signature(connection, signature)
        restored_count = restore_listing_ids(connection, listing_ids)
        review = _fetch_listing_review_payload(connection, listing_id)
        connection.commit()

    return {
        "listing_id": listing_id,
        "server": signature.server,
        "action": "restore_similar",
        "disabled_rule_count": len(disabled_rules),
        "disabled_rules": [_discard_rule_payload(rule) for rule in disabled_rules],
        "matched_count": len(listing_ids),
        "restored_count": restored_count,
        "review": review,
    }


@router.get("/api/listings/recent")
def recent_listings(
    request: Request,
    server: str = Query("frostreaver", min_length=1),
    q: str | None = Query(None),
    limit: int = Query(DEFAULT_LIMIT, gt=0, le=500),
    offset: int = Query(0, ge=0),
    review_status: ListingReviewStatusFilter = Query("all"),
    interest_status: ItemInterestFilter = Query("tracked"),
) -> list[dict[str, Any]]:
    db_server = _normalize_server(server)
    search_text = _normalize_search(q)

    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        return _fetch_recent_listings(
            connection,
            db_server,
            search_text=search_text,
            review_status=review_status,
            interest_status=interest_status,
            limit=limit,
            offset=offset,
        )


def _fetch_recent_listings(
    connection: sqlite3.Connection,
    db_server: str,
    *,
    search_text: str | None,
    review_status: ListingReviewStatusFilter,
    interest_status: ItemInterestFilter,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    search_filter = ""
    status_filter = ""
    interest_filter = _item_interest_filter_clause(LISTING_ITEM_PREFERENCE_EXPRESSION, interest_status)
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

    if review_status != "all":
        status_filter = "AND COALESCE(mlr.status, 'active') = ?"
        params.append(review_status)

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
            ml.raw_line,
            ml.source,
            ml.confidence,
            {LISTING_ITEM_PREFERENCE_EXPRESSION} AS item_preference,
            COALESCE(mlr.status, 'active') AS review_status,
            mlr.reason_code AS review_reason_code,
            mlr.note AS review_note
        FROM market_listings ml
        LEFT JOIN items i
            ON i.item_id = ml.item_id
        LEFT JOIN market_listing_reviews mlr
            ON mlr.listing_id = ml.listing_id
        WHERE lower(ml.server) = ?
{search_filter}
          {status_filter}
          {interest_filter}
        ORDER BY datetime(ml.timestamp) DESC, ml.timestamp DESC, ml.listing_id DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()

    listings = [_listing_payload(row) for row in rows]
    _attach_item_sources(connection, listings)
    return listings


def _attach_item_sources(connection: sqlite3.Connection, listings: list[dict[str, Any]]) -> None:
    item_ids = {
        int(item_id)
        for listing in listings
        if (item_id := listing["item"]["item_id"]) is not None
    }
    sources_by_item_id = fetch_item_sources_by_id(connection, item_ids)
    for listing in listings:
        item_id = listing["item"]["item_id"]
        listing["item"]["sources"] = sources_by_item_id.get(int(item_id), []) if item_id is not None else []


def _listing_payload(row: sqlite3.Row) -> dict[str, Any]:
    item_id = _optional_int(row["item_id"])

    return {
        "listing_id": int(row["listing_id"]),
        "timestamp": row["timestamp"],
        "seller": row["seller"],
        "item": {
            "item_id": item_id,
            "name": row["item_name"],
            "sources": [],
        },
        "item_id": item_id,
        "item_name": row["item_name"],
        "price_raw": row["price_raw"],
        "raw_line": row["raw_line"],
        "price_pp": _optional_int(row["price_pp"]),
        "source": row["source"],
        "confidence": row["confidence"],
        "resolved": item_id is not None,
        "review_status": row["review_status"],
        "review_reason_code": row["review_reason_code"],
        "review_note": row["review_note"],
        "item_preference": row["item_preference"],
    }


def _upsert_listing_review(
    connection: sqlite3.Connection,
    listing_id: int,
    *,
    status: ListingReviewStatus,
    reason_code: str | None,
    note: str | None,
) -> dict[str, Any]:
    listing = connection.execute(
        """
        SELECT listing_id, server
        FROM market_listings
        WHERE listing_id = ?
        """,
        (listing_id,),
    ).fetchone()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    connection.execute(
        """
        INSERT INTO market_listing_reviews (listing_id, status, reason_code, note, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(listing_id) DO UPDATE SET
            status = excluded.status,
            reason_code = excluded.reason_code,
            note = excluded.note,
            updated_at = CURRENT_TIMESTAMP
        """,
        (listing_id, status, reason_code, note),
    )

    return _fetch_listing_review_payload(connection, listing_id)


def _fetch_listing_review_payload(connection: sqlite3.Connection, listing_id: int) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT
            mlr.listing_id,
            ml.server,
            mlr.status,
            mlr.reason_code,
            mlr.note,
            mlr.created_at,
            mlr.updated_at
        FROM market_listing_reviews mlr
        JOIN market_listings ml
            ON ml.listing_id = mlr.listing_id
        WHERE mlr.listing_id = ?
        """,
        (listing_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Listing review not found")
    return _listing_review_payload(row)


def _listing_review_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "listing_id": int(row["listing_id"]),
        "server": row["server"],
        "status": row["status"],
        "reason_code": row["reason_code"],
        "note": row["note"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _discard_rule_payload(rule: DiscardRule) -> dict[str, Any]:
    return {
        "rule_id": rule.rule_id,
        "enabled": rule.enabled,
        "server": rule.server,
        "seller": rule.seller,
        "item_id": rule.item_id,
        "price_currency": rule.price_currency,
        "price_amount": rule.price_amount,
        "price_pp": rule.price_pp,
        "reason_code": rule.reason_code,
        "note": rule.note,
        "source_listing_id": rule.source_listing_id,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
        "disabled_at": rule.disabled_at,
    }


def _item_interest_filter_clause(expression: str, interest_status: ItemInterestFilter) -> str:
    if interest_status == "all":
        return ""
    if interest_status == "wanted":
        return f"AND {expression} = 'wanted'"
    if interest_status == "ignored":
        return f"AND {expression} = 'ignored'"
    return f"AND COALESCE({expression}, 'neutral') != 'ignored'"


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


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _connect_or_503(db_path: str | Path) -> sqlite3.Connection:
    try:
        return connect_readonly(db_path)
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"SQLite database is not readable: {exc}") from exc


def _connect_writable_or_503(db_path: str | Path) -> sqlite3.Connection:
    try:
        resolved_path = Path(db_path)
        init_db(resolved_path)
        connection = sqlite3.connect(resolved_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"SQLite database is not writable: {exc}") from exc


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)

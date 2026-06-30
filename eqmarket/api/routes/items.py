from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from eqmarket.api.db import connect_readonly
from eqmarket.api.item_sources import fetch_item_sources
from eqmarket.log_parser import normalize_item_name
from eqmarket.slot_masks import decode_lucy_slot_mask
from eqmarket.sources.tlp_auctions import PricePoint, TlpAuctionsClient, TlpAuctionsError


DEFAULT_SEARCH_LIMIT = 20
DEFAULT_LISTINGS_LIMIT = 100

ITEM_COLUMNS = """
    item_id,
    name,
    normalized_name,
    item_type,
    slot,
    classes,
    races,
    ac,
    hp,
    mana,
    endurance,
    hp_regen,
    mana_regen,
    endurance_regen,
    astr,
    asta,
    aagi,
    adex,
    awis,
    aint,
    acha,
    heroic_str,
    heroic_sta,
    heroic_agi,
    heroic_dex,
    heroic_wis,
    heroic_int,
    heroic_cha,
    sv_magic,
    sv_fire,
    sv_cold,
    sv_poison,
    sv_disease,
    damage,
    delay,
    ratio,
    haste,
    required_level,
    recommended_level,
    icon_id,
    flags,
    source_primary,
    last_imported_at
"""


router = APIRouter()


@router.get("/api/items/search")
def search_items(
    request: Request,
    q: str = Query(..., min_length=1),
    server: str = Query("frostreaver", min_length=1),
    limit: int = Query(DEFAULT_SEARCH_LIMIT, gt=0, le=100),
) -> list[dict[str, Any]]:
    db_server = _normalize_server(server)
    search_text = _normalize_required_text(q, "q")

    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        rows = connection.execute(
            """
            SELECT
                i.item_id,
                i.name,
                i.slot,
                i.classes,
                i.flags,
                COALESCE(
                    (
                        SELECT ip.status
                        FROM item_preferences ip
                        WHERE ip.server = ?
                          AND ip.preference_key_kind = 'item_id'
                          AND ip.preference_key = CAST(i.item_id AS TEXT)
                    ),
                    (
                        SELECT ip.status
                        FROM item_preferences ip
                        WHERE ip.server = ?
                          AND ip.preference_key_kind = 'name'
                          AND ip.preference_key = i.normalized_name
                    )
                ) AS item_preference
            FROM items i
            WHERE i.normalized_name LIKE ? ESCAPE '\\'
               OR lower(i.name) LIKE ? ESCAPE '\\'
            ORDER BY
                CASE
                    WHEN i.normalized_name = ? THEN 0
                    WHEN i.normalized_name LIKE ? ESCAPE '\\' THEN 1
                    ELSE 2
                END,
                i.name COLLATE NOCASE
            LIMIT ?
            """,
            (
                db_server,
                db_server,
                _like_pattern(search_text),
                _like_pattern(search_text),
                search_text,
                _prefix_like_pattern(search_text),
                limit,
            ),
        ).fetchall()

    return [
        {
            "item_id": int(row["item_id"]),
            "name": row["name"],
            "icon_url": None,
            **_slot_payload(row["slot"]),
            "classes": row["classes"],
            "flags": row["flags"],
            "item_preference": row["item_preference"],
        }
        for row in rows
    ]


@router.get("/api/items/tooltip")
def item_tooltip_by_name(
    request: Request,
    name: str = Query(..., min_length=1),
    server: str = Query("frostreaver", min_length=1),
) -> dict[str, Any]:
    db_server = _normalize_server(server)
    normalized_name = _normalize_required_item_name(name)

    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        item = _fetch_item_by_normalized_name(connection, normalized_name)
        if item is None:
            raise _item_not_found()
        return _tooltip_payload(connection, item, db_server)


@router.get("/api/items/{item_id}")
def item_detail(
    request: Request,
    item_id: int,
    server: str = Query("frostreaver", min_length=1),
) -> dict[str, Any]:
    db_server = _normalize_server(server)

    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        item = _fetch_item_or_404(connection, item_id)
        effects = _fetch_item_effects(connection, item_id)
        sources = fetch_item_sources(connection, item_id)
        item_preference = _fetch_item_preference_status(connection, item, db_server)

    return _item_detail_payload(item, effects, sources, item_preference)


@router.get("/api/items/{item_id}/prices")
def item_prices(
    request: Request,
    item_id: int,
    server: str = Query("frostreaver", min_length=1),
) -> dict[str, Any]:
    db_server = _normalize_server(server)

    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        _fetch_item_or_404(connection, item_id)
        price = _fetch_price_payload(connection, item_id, db_server)

    return price


@router.get("/api/items/{item_id}/tlp-history")
def item_tlp_history(
    request: Request,
    item_id: int,
    server: str = Query("frostreaver", min_length=1),
) -> list[dict[str, Any]]:
    db_server = _normalize_server(server)

    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        _fetch_item_or_404(connection, item_id)
        krono_price_pp = _fetch_latest_krono_price(connection, db_server)

    try:
        points = TlpAuctionsClient().get_item_history(item_id, db_server)
    except (OSError, TlpAuctionsError) as exc:
        raise HTTPException(status_code=502, detail=f"TLP Auctions item history failed: {exc}") from exc

    history = [
        payload
        for point in points
        if (payload := _tlp_history_point_payload(point, krono_price_pp)) is not None
    ]
    return sorted(history, key=lambda point: point["timestamp"])


@router.get("/api/items/{item_id}/listings")
def item_listings(
    request: Request,
    item_id: int,
    server: str = Query("frostreaver", min_length=1),
    limit: int = Query(DEFAULT_LISTINGS_LIMIT, gt=0, le=500),
) -> list[dict[str, Any]]:
    db_server = _normalize_server(server)

    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        item = _fetch_item_or_404(connection, item_id)
        return _fetch_item_listings(connection, item, db_server, limit)


@router.get("/api/items/{item_id}/tooltip")
def item_tooltip(
    request: Request,
    item_id: int,
    server: str = Query("frostreaver", min_length=1),
) -> dict[str, Any]:
    db_server = _normalize_server(server)

    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        item = _fetch_item_or_404(connection, item_id)
        return _tooltip_payload(connection, item, db_server)


def _fetch_item_or_404(connection: sqlite3.Connection, item_id: int) -> sqlite3.Row:
    item = _fetch_item(connection, item_id)
    if item is None:
        raise _item_not_found()
    return item


def _fetch_item(connection: sqlite3.Connection, item_id: int) -> sqlite3.Row | None:
    return connection.execute(
        f"""
        SELECT {ITEM_COLUMNS}
        FROM items
        WHERE item_id = ?
        """,
        (item_id,),
    ).fetchone()


def _fetch_item_by_normalized_name(connection: sqlite3.Connection, normalized_name: str) -> sqlite3.Row | None:
    return connection.execute(
        f"""
        SELECT {ITEM_COLUMNS}
        FROM items
        WHERE normalized_name = ?
        """,
        (normalized_name,),
    ).fetchone()


def _fetch_item_effects(connection: sqlite3.Connection, item_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            ie.effect_slot,
            ie.trigger_type,
            ie.effect_type_raw,
            ie.cast_time_ms,
            ie.required_level,
            ie.effective_level,
            ie.proc_rate,
            ie.charges,
            ie.description,
            s.spell_id,
            s.name AS spell_name,
            s.spell_type,
            s.target_type,
            s.skill
        FROM item_effects ie
        LEFT JOIN spells s
            ON s.spell_id = ie.spell_id
        WHERE ie.item_id = ?
        ORDER BY ie.effect_slot
        """,
        (item_id,),
    ).fetchall()

    return [_effect_payload(row) for row in rows]


def _fetch_price_payload(connection: sqlite3.Connection, item_id: int, db_server: str) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT
            item_id,
            server,
            median_pp,
            p25_pp,
            p75_pp,
            avg_pp,
            min_pp,
            max_pp,
            sample_size,
            confidence,
            last_refresh_at,
            source,
            COALESCE(NULLIF(median_pp, 0), NULLIF(avg_pp, 0), NULLIF(p25_pp, 0)) AS market_price_pp,
            CASE
                WHEN median_pp IS NOT NULL AND median_pp > 0 THEN 'median_pp'
                WHEN avg_pp IS NOT NULL AND avg_pp > 0 THEN 'avg_pp'
                WHEN p25_pp IS NOT NULL AND p25_pp > 0 THEN 'p25_pp'
                ELSE NULL
            END AS market_price_source
        FROM market_prices
        WHERE item_id = ?
          AND lower(server) = ?
        LIMIT 1
        """,
        (item_id, db_server),
    ).fetchone()

    if row is None:
        return {
            "item_id": item_id,
            "server": db_server,
            "market_price_pp": None,
            "market_price_source": None,
            "median_pp": None,
            "p25_pp": None,
            "p75_pp": None,
            "avg_pp": None,
            "min_pp": None,
            "max_pp": None,
            "sample_size": None,
            "confidence": None,
            "last_refresh_at": None,
            "source": None,
        }

    return {
        "item_id": int(row["item_id"]),
        "server": row["server"],
        "market_price_pp": _optional_int(row["market_price_pp"]),
        "market_price_source": row["market_price_source"],
        "median_pp": _optional_int(row["median_pp"]),
        "p25_pp": _optional_int(row["p25_pp"]),
        "p75_pp": _optional_int(row["p75_pp"]),
        "avg_pp": _optional_int(row["avg_pp"]),
        "min_pp": _optional_int(row["min_pp"]),
        "max_pp": _optional_int(row["max_pp"]),
        "sample_size": _optional_int(row["sample_size"]),
        "confidence": row["confidence"],
        "last_refresh_at": row["last_refresh_at"],
        "source": row["source"],
    }


def _fetch_last_seen_payload(connection: sqlite3.Connection, item_id: int, db_server: str) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT ml.timestamp, ml.seller, ml.price_raw, ml.price_pp
        FROM market_listings ml
        LEFT JOIN market_listing_reviews mlr
            ON mlr.listing_id = ml.listing_id
        WHERE ml.item_id = ?
          AND lower(ml.server) = ?
          AND ml.price_pp IS NOT NULL
          AND COALESCE(mlr.status, 'active') = 'active'
        ORDER BY datetime(ml.timestamp) DESC, ml.timestamp DESC, ml.listing_id DESC
        LIMIT 1
        """,
        (item_id, db_server),
    ).fetchone()

    if row is None:
        return {
            "last_seen_pp": None,
            "last_seen_at": None,
            "last_seen_seller": None,
            "last_seen_price_raw": None,
        }

    return {
        "last_seen_pp": _optional_int(row["price_pp"]),
        "last_seen_at": row["timestamp"],
        "last_seen_seller": row["seller"],
        "last_seen_price_raw": row["price_raw"],
    }


def _fetch_latest_krono_price(connection: sqlite3.Connection, db_server: str) -> int | None:
    row = connection.execute(
        """
        SELECT price_pp
        FROM krono_prices
        WHERE lower(server) = ?
          AND price_pp IS NOT NULL
        ORDER BY datetime(last_refresh_at) DESC
        LIMIT 1
        """,
        (db_server,),
    ).fetchone()
    return _optional_int(row["price_pp"]) if row else None


def _fetch_item_preference_status(connection: sqlite3.Connection, item: sqlite3.Row, db_server: str) -> str | None:
    row = connection.execute(
        """
        SELECT COALESCE(
            (
                SELECT ip.status
                FROM item_preferences ip
                WHERE ip.server = ?
                  AND ip.preference_key_kind = 'item_id'
                  AND ip.preference_key = CAST(? AS TEXT)
            ),
            (
                SELECT ip.status
                FROM item_preferences ip
                WHERE ip.server = ?
                  AND ip.preference_key_kind = 'name'
                  AND ip.preference_key = ?
            )
        ) AS item_preference
        """,
        (db_server, int(item["item_id"]), db_server, item["normalized_name"]),
    ).fetchone()
    return row["item_preference"] if row is not None else None


def _tlp_history_point_payload(point: PricePoint, krono_price_pp: int | None) -> dict[str, Any] | None:
    if point.is_buy:
        return None

    price_pp = point.plat_price
    krono_price_pp_used = None
    if point.krono_price > 0:
        if krono_price_pp is None:
            return None
        price_pp += point.krono_price * krono_price_pp
        krono_price_pp_used = krono_price_pp

    if price_pp <= 0:
        return None

    return {
        "timestamp": point.datetime,
        "price_pp": round(price_pp),
        "plat_price": point.plat_price,
        "krono_price": point.krono_price,
        "krono_price_pp_used": krono_price_pp_used,
        "seller": point.auctioneer,
        "source": "tlp_auctions_history",
    }


def _fetch_item_listings(
    connection: sqlite3.Connection,
    item: sqlite3.Row,
    db_server: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            ml.listing_id,
            ml.timestamp,
            ml.seller,
            ml.item_id,
            ml.item_name,
            ml.price_raw,
            ml.price_pp,
            ml.raw_line,
            ml.source,
            ml.confidence,
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
                      AND ip.preference_key = ?
                ),
                (
                    SELECT ip.status
                    FROM item_preferences ip
                    WHERE ip.server = lower(ml.server)
                      AND ip.preference_key_kind = 'name'
                      AND ip.preference_key = ml.normalized_item_name
                )
            ) AS item_preference,
            COALESCE(mlr.status, 'active') AS review_status,
            mlr.reason_code AS review_reason_code,
            mlr.note AS review_note
        FROM market_listings ml
        LEFT JOIN market_listing_reviews mlr
            ON mlr.listing_id = ml.listing_id
        WHERE ml.item_id = ?
          AND lower(ml.server) = ?
        ORDER BY datetime(ml.timestamp) DESC, ml.timestamp DESC, ml.listing_id DESC
        LIMIT ?
        """,
        (item["normalized_name"], int(item["item_id"]), db_server, limit),
    ).fetchall()

    return [_listing_payload(row, item["name"]) for row in rows]


def _item_detail_payload(
    item: sqlite3.Row,
    effects: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    item_preference: str | None,
) -> dict[str, Any]:
    return {
        "item_id": int(item["item_id"]),
        "name": item["name"],
        "icon_url": None,
        "icon_id": _optional_int(item["icon_id"]),
        "item_type": item["item_type"],
        **_slot_payload(item["slot"]),
        "classes": item["classes"],
        "races": item["races"],
        "flags": item["flags"],
        "stats": _stats_payload(item),
        "combat": _combat_payload(item),
        "levels": _levels_payload(item),
        "effects": effects,
        "sources": sources,
        "source_primary": item["source_primary"],
        "last_imported_at": item["last_imported_at"],
        "item_preference": item_preference,
    }


def _tooltip_payload(connection: sqlite3.Connection, item: sqlite3.Row, db_server: str) -> dict[str, Any]:
    price = _fetch_price_payload(connection, int(item["item_id"]), db_server)
    last_seen = _fetch_last_seen_payload(connection, int(item["item_id"]), db_server)
    effects = _fetch_item_effects(connection, int(item["item_id"]))
    sources = fetch_item_sources(connection, int(item["item_id"]))
    item_preference = _fetch_item_preference_status(connection, item, db_server)
    stats = _stats_payload(item)
    combat = _combat_payload(item)
    levels = _levels_payload(item)

    return {
        "item_id": int(item["item_id"]),
        "name": item["name"],
        "icon_url": None,
        **_slot_payload(item["slot"]),
        "classes": item["classes"],
        "races": item["races"],
        "item_type": item["item_type"],
        "flags": item["flags"],
        "server": db_server,
        **stats,
        **combat,
        **levels,
        "market_price_pp": price["market_price_pp"],
        "market_price_source": price["market_price_source"],
        "median_pp": price["median_pp"],
        "p25_pp": price["p25_pp"],
        "p75_pp": price["p75_pp"],
        "avg_pp": price["avg_pp"],
        "sample_size": price["sample_size"],
        "confidence": price["confidence"],
        "last_refresh_at": price["last_refresh_at"],
        **last_seen,
        "effects": effects,
        "sources": sources,
        "item_preference": item_preference,
    }


def _slot_payload(raw_slot: Any) -> dict[str, Any]:
    decoded = decode_lucy_slot_mask(raw_slot)
    return {
        "slot": decoded.slot_display,
        "slot_mask": decoded.slot_mask,
        "slot_labels": list(decoded.slot_labels),
        "slot_display": decoded.slot_display,
    }


def _stats_payload(item: sqlite3.Row) -> dict[str, Any]:
    return {
        "ac": _optional_int(item["ac"]),
        "hp": _optional_int(item["hp"]),
        "mana": _optional_int(item["mana"]),
        "endurance": _optional_int(item["endurance"]),
        "hp_regen": _optional_int(item["hp_regen"]),
        "mana_regen": _optional_int(item["mana_regen"]),
        "endurance_regen": _optional_int(item["endurance_regen"]),
        "str": _optional_int(item["astr"]),
        "sta": _optional_int(item["asta"]),
        "agi": _optional_int(item["aagi"]),
        "dex": _optional_int(item["adex"]),
        "wis": _optional_int(item["awis"]),
        "int": _optional_int(item["aint"]),
        "cha": _optional_int(item["acha"]),
        "heroic_str": _optional_int(item["heroic_str"]),
        "heroic_sta": _optional_int(item["heroic_sta"]),
        "heroic_agi": _optional_int(item["heroic_agi"]),
        "heroic_dex": _optional_int(item["heroic_dex"]),
        "heroic_wis": _optional_int(item["heroic_wis"]),
        "heroic_int": _optional_int(item["heroic_int"]),
        "heroic_cha": _optional_int(item["heroic_cha"]),
        "sv_magic": _optional_int(item["sv_magic"]),
        "sv_fire": _optional_int(item["sv_fire"]),
        "sv_cold": _optional_int(item["sv_cold"]),
        "sv_poison": _optional_int(item["sv_poison"]),
        "sv_disease": _optional_int(item["sv_disease"]),
    }


def _combat_payload(item: sqlite3.Row) -> dict[str, Any]:
    return {
        "damage": _optional_int(item["damage"]),
        "delay": _optional_int(item["delay"]),
        "ratio": _optional_float(item["ratio"]),
        "haste": _optional_int(item["haste"]),
    }


def _levels_payload(item: sqlite3.Row) -> dict[str, Any]:
    return {
        "required_level": _optional_int(item["required_level"]),
        "recommended_level": _optional_int(item["recommended_level"]),
    }


def _effect_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "effect_slot": int(row["effect_slot"]),
        "trigger_type": row["trigger_type"],
        "effect_type_raw": _optional_int(row["effect_type_raw"]),
        "spell": {
            "spell_id": _optional_int(row["spell_id"]),
            "name": row["spell_name"],
            "spell_type": row["spell_type"],
            "target_type": row["target_type"],
            "skill": row["skill"],
        },
        "cast_time_ms": _optional_int(row["cast_time_ms"]),
        "required_level": _optional_int(row["required_level"]),
        "effective_level": _optional_int(row["effective_level"]),
        "proc_rate": _optional_int(row["proc_rate"]),
        "charges": _optional_int(row["charges"]),
        "description": row["description"] or row["spell_name"],
    }


def _listing_payload(row: sqlite3.Row, canonical_item_name: str) -> dict[str, Any]:
    item_id = _optional_int(row["item_id"])

    return {
        "listing_id": int(row["listing_id"]),
        "timestamp": row["timestamp"],
        "seller": row["seller"],
        "item": {
            "item_id": item_id,
            "name": canonical_item_name,
        },
        "item_id": item_id,
        "item_name": canonical_item_name,
        "listed_item_name": row["item_name"],
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


def _normalize_server(server: str) -> str:
    db_server = server.strip().lower()
    if not db_server:
        raise HTTPException(status_code=400, detail="server must not be blank")
    return db_server


def _normalize_required_text(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail=f"{field_name} must not be blank")
    return normalized


def _normalize_required_item_name(name: str) -> str:
    normalized_name = normalize_item_name(name)
    if not normalized_name:
        raise HTTPException(status_code=400, detail="name must not be blank")
    return normalized_name


def _like_pattern(value: str) -> str:
    return f"%{_escape_like(value)}%"


def _prefix_like_pattern(value: str) -> str:
    return f"{_escape_like(value)}%"


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _connect_or_503(db_path: str | Path) -> sqlite3.Connection:
    try:
        return connect_readonly(db_path)
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"SQLite database is not readable: {exc}") from exc


def _item_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Item not found")


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)

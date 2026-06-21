from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from eqmarket.api.db import connect_readonly
from eqmarket.db import init_db
from eqmarket.price_importer import (
    INVENTORY_EXCLUDED_ITEM_TYPES,
    INVENTORY_EXCLUDED_NORMALIZED_NAMES,
)


DecisionStatus = Literal["keep", "sell", "ignore"]
DecisionScope = Literal["global", "character"]

NON_EQUIPMENT_INVENTORY_AREAS = ("carried", "bank", "shared_bank")
AREA_ORDER = {"carried": 0, "bank": 1, "shared_bank": 2}
DEFAULT_SERVER = "frostreaver"
DEFAULT_LOCAL_LISTING_MAX_AGE_DAYS = 30

SELL_CANDIDATE_CATEGORIES = ("sellable", "keep", "ignored", "no_drop", "unpriced", "excluded")


class InventoryItemDecisionUpdate(BaseModel):
    status: DecisionStatus
    notes: str | None = None


router = APIRouter()


@router.get("/api/characters/{character_name}/sell-candidates")
def character_sell_candidates(
    character_name: str,
    request: Request,
    local_listing_max_age_days: int = Query(DEFAULT_LOCAL_LISTING_MAX_AGE_DAYS, ge=1, le=3650),
) -> dict[str, Any]:
    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        character = _fetch_character_or_404(connection, character_name)
        rows = _fetch_sell_candidate_rows(
            connection,
            character_name=character["character_name"],
            server=None,
            local_listing_max_age_days=local_listing_max_age_days,
        )

    return _sell_candidates_payload(
        rows,
        scope="character",
        character_name=character["character_name"],
        server=_normalize_optional_server(character["server"]),
        local_listing_max_age_days=local_listing_max_age_days,
    )


@router.get("/api/inventory/sell-candidates")
def inventory_sell_candidates(
    request: Request,
    server: str | None = Query(None, min_length=1),
    local_listing_max_age_days: int = Query(DEFAULT_LOCAL_LISTING_MAX_AGE_DAYS, ge=1, le=3650),
) -> dict[str, Any]:
    db_server = _normalize_optional_server(server)

    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        rows = _fetch_sell_candidate_rows(
            connection,
            character_name=None,
            server=db_server,
            local_listing_max_age_days=local_listing_max_age_days,
        )

    return _sell_candidates_payload(
        rows,
        scope="global",
        character_name=None,
        server=db_server,
        local_listing_max_age_days=local_listing_max_age_days,
    )


@router.put("/api/characters/{character_name}/inventory/items/{item_id}/decision")
def update_character_inventory_item_decision(
    character_name: str,
    item_id: int,
    payload: InventoryItemDecisionUpdate,
    request: Request,
) -> dict[str, Any]:
    notes = _normalize_optional_text(payload.notes)

    with closing(_connect_writable_or_503(request.app.state.db_path)) as connection:
        character = _fetch_character_or_404(connection, character_name)
        target = _fetch_decision_target(connection, item_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Item not found")

        decision = _upsert_inventory_item_decision(
            connection,
            target,
            server=_server_for_character(character),
            scope="character",
            character_name=character["character_name"],
            status=payload.status,
            notes=notes,
        )
        connection.commit()

    return decision


@router.delete("/api/characters/{character_name}/inventory/items/{item_id}/decision")
def clear_character_inventory_item_decision(
    character_name: str,
    item_id: int,
    request: Request,
) -> dict[str, Any]:
    with closing(_connect_writable_or_503(request.app.state.db_path)) as connection:
        character = _fetch_character_or_404(connection, character_name)
        target = _fetch_decision_target(connection, item_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Item not found")

        decision = _delete_inventory_item_decision(
            connection,
            target,
            server=_server_for_character(character),
            scope="character",
            character_name=character["character_name"],
        )
        connection.commit()

    return decision


@router.put("/api/inventory/items/{item_id}/decision")
def update_global_inventory_item_decision(
    item_id: int,
    payload: InventoryItemDecisionUpdate,
    request: Request,
    server: str = Query(DEFAULT_SERVER, min_length=1),
) -> dict[str, Any]:
    db_server = _normalize_required_server(server)
    notes = _normalize_optional_text(payload.notes)

    with closing(_connect_writable_or_503(request.app.state.db_path)) as connection:
        target = _fetch_decision_target(connection, item_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Item not found")

        decision = _upsert_inventory_item_decision(
            connection,
            target,
            server=db_server,
            scope="global",
            character_name=None,
            status=payload.status,
            notes=notes,
        )
        connection.commit()

    return decision


@router.delete("/api/inventory/items/{item_id}/decision")
def clear_global_inventory_item_decision(
    item_id: int,
    request: Request,
    server: str = Query(DEFAULT_SERVER, min_length=1),
) -> dict[str, Any]:
    db_server = _normalize_required_server(server)

    with closing(_connect_writable_or_503(request.app.state.db_path)) as connection:
        target = _fetch_decision_target(connection, item_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Item not found")

        decision = _delete_inventory_item_decision(
            connection,
            target,
            server=db_server,
            scope="global",
            character_name=None,
        )
        connection.commit()

    return decision


def _fetch_sell_candidate_rows(
    connection: sqlite3.Connection,
    *,
    character_name: str | None,
    server: str | None,
    local_listing_max_age_days: int,
) -> list[sqlite3.Row]:
    filters: list[str] = ["cii.area IN ('carried', 'bank', 'shared_bank')"]
    params: list[Any] = [f"-{local_listing_max_age_days} days"]

    if character_name is not None:
        filters.append("lower(cii.character_name) = ?")
        params.append(character_name.strip().lower())
    if server is not None:
        filters.append("lower(cii.server) = ?")
        params.append(server)

    where_clause = "\n          AND ".join(filters)

    return connection.execute(
        f"""
        WITH recent_listing_prices AS (
            SELECT
                ml.item_id,
                lower(ml.server) AS server,
                CAST(ROUND(AVG(ml.price_pp)) AS INTEGER) AS listing_price_pp,
                COUNT(*) AS listing_sample_size,
                MAX(ml.timestamp) AS listing_last_seen_at
            FROM market_listings ml
            LEFT JOIN market_listing_reviews mlr
                ON mlr.listing_id = ml.listing_id
            WHERE ml.item_id IS NOT NULL
              AND ml.price_pp IS NOT NULL
              AND ml.price_pp > 0
              AND COALESCE(mlr.status, 'active') = 'active'
              AND datetime(ml.timestamp) >= datetime('now', ?)
            GROUP BY ml.item_id, lower(ml.server)
        ),
        inventory_groups AS (
            SELECT
                cii.character_name,
                lower(cii.server) AS server,
                cii.item_id,
                COALESCE(NULLIF(i.name, ''), cii.item_name) AS item_name,
                COALESCE(NULLIF(i.normalized_name, ''), cii.normalized_item_name) AS normalized_item_name,
                i.item_type,
                i.flags,
                i.source_primary,
                i.icon_id,
                i.last_imported_at,
                SUM(cii.quantity) AS quantity,
                SUM(CASE WHEN cii.area = 'carried' THEN cii.quantity ELSE 0 END) AS carried_quantity,
                SUM(CASE WHEN cii.area = 'bank' THEN cii.quantity ELSE 0 END) AS bank_quantity,
                SUM(CASE WHEN cii.area = 'shared_bank' THEN cii.quantity ELSE 0 END) AS shared_bank_quantity,
                COUNT(*) AS location_count,
                MAX(COALESCE(cii.is_starter_item, 0)) AS is_starter_item,
                MAX(COALESCE(cii.is_container, 0)) AS is_container,
                MAX(COALESCE(cii.is_augment, 0)) AS is_augment,
                GROUP_CONCAT(DISTINCT cii.area) AS areas_csv,
                GROUP_CONCAT(DISTINCT cii.raw_item_name) AS raw_item_names_csv
            FROM character_inventory_items cii
            LEFT JOIN items i
                ON i.item_id = cii.item_id
            WHERE {where_clause}
            GROUP BY cii.character_name, lower(cii.server), cii.item_id
        )
        SELECT
            inv.*,
            mp.median_pp,
            mp.p25_pp,
            mp.p75_pp,
            mp.avg_pp,
            mp.min_pp,
            mp.max_pp,
            mp.sample_size AS market_sample_size,
            mp.confidence AS market_confidence,
            mp.last_refresh_at AS market_last_refresh_at,
            mp.source AS market_source,
            mpo.price_amount AS override_price_amount,
            lower(mpo.price_currency) AS override_price_currency,
            mpo.confidence AS override_confidence,
            mpo.notes AS override_notes,
            kp.price_pp AS krono_price_pp,
            rlp.listing_price_pp,
            rlp.listing_sample_size,
            rlp.listing_last_seen_at,
            cd.decision_id AS character_decision_id,
            cd.status AS character_decision_status,
            cd.notes AS character_decision_notes,
            cd.created_at AS character_decision_created_at,
            cd.updated_at AS character_decision_updated_at,
            gd.decision_id AS global_decision_id,
            gd.status AS global_decision_status,
            gd.notes AS global_decision_notes,
            gd.created_at AS global_decision_created_at,
            gd.updated_at AS global_decision_updated_at
        FROM inventory_groups inv
        LEFT JOIN market_prices mp
            ON mp.item_id = inv.item_id
           AND lower(mp.server) = inv.server
        LEFT JOIN market_prices_override mpo
            ON mpo.item_id = inv.item_id
           AND lower(mpo.server) = inv.server
        LEFT JOIN krono_prices kp
            ON lower(kp.server) = inv.server
        LEFT JOIN recent_listing_prices rlp
            ON rlp.item_id = inv.item_id
           AND rlp.server = inv.server
        LEFT JOIN inventory_item_decisions cd
            ON cd.server = inv.server
           AND cd.scope = 'character'
           AND cd.scope_key = lower(inv.character_name)
           AND cd.item_id = inv.item_id
        LEFT JOIN inventory_item_decisions gd
            ON gd.server = inv.server
           AND gd.scope = 'global'
           AND gd.scope_key = '*'
           AND gd.item_id = inv.item_id
        ORDER BY lower(inv.character_name), lower(inv.item_name), inv.item_id
        """,
        params,
    ).fetchall()


def _sell_candidates_payload(
    rows: list[sqlite3.Row],
    *,
    scope: str,
    character_name: str | None,
    server: str | None,
    local_listing_max_age_days: int,
) -> dict[str, Any]:
    items = [_candidate_payload(row) for row in rows]
    items.sort(key=_candidate_sort_key)
    categories = _categorize_items(items)
    sellable_total = sum(item["estimated_total_pp"] or 0 for item in categories["sellable"])

    return {
        "scope": scope,
        "character_name": character_name,
        "server": server,
        "local_listing_max_age_days": local_listing_max_age_days,
        "item_count": len(items),
        "total_quantity": sum(int(item["quantity"]) for item in items),
        "sellable_total_value_pp": sellable_total,
        "categories": categories,
        "items": items,
        "global_items": _global_item_rollups(items),
    }


def _candidate_payload(row: sqlite3.Row) -> dict[str, Any]:
    unit_price_pp, price_source, price_source_detail, confidence, sample_size, price_seen_at = _estimated_price(row)
    quantity = _as_int(row["quantity"]) or 0
    estimated_total_pp = unit_price_pp * quantity if unit_price_pp is not None else None
    flags = row["flags"]
    is_starter_item = bool(row["is_starter_item"])
    is_no_trade_import = _is_no_trade_import(is_starter_item, flags)
    is_no_drop = "NO_DROP" in _flag_tokens(flags)
    is_container = bool(row["is_container"])
    is_consumable = _is_excluded_consumable(row["normalized_item_name"], row["item_type"])
    exclusion_reasons = _default_exclusion_reasons(
        is_starter_item=is_starter_item,
        is_no_trade_import=is_no_trade_import,
        is_container=is_container,
        is_consumable=is_consumable,
    )
    decision = _decision_payload(row)
    category = _candidate_category(
        decision_status=decision["status"] if decision is not None else None,
        has_price=unit_price_pp is not None,
        is_no_drop=is_no_drop,
        exclusion_reasons=exclusion_reasons,
    )

    return {
        "character_name": row["character_name"],
        "server": row["server"],
        "item_id": int(row["item_id"]),
        "item_name": row["item_name"],
        "name": row["item_name"],
        "normalized_item_name": row["normalized_item_name"],
        "quantity": quantity,
        "areas": _sorted_areas(row["areas_csv"]),
        "area_quantities": _area_quantities(row),
        "location_count": _as_int(row["location_count"]) or 0,
        "raw_item_names": _csv_values(row["raw_item_names_csv"]),
        "item_type": row["item_type"],
        "flags": flags,
        "source_primary": row["source_primary"],
        "icon_id": _as_int(row["icon_id"]),
        "last_imported_at": row["last_imported_at"],
        "is_starter_item": is_starter_item,
        "is_no_trade_import": is_no_trade_import,
        "is_no_drop": is_no_drop,
        "is_container": is_container,
        "is_consumable": is_consumable,
        "is_augment": bool(row["is_augment"]),
        "default_exclusion_reasons": exclusion_reasons,
        "decision_status": decision["status"] if decision is not None else None,
        "decision": decision,
        "estimated_unit_price_pp": unit_price_pp,
        "estimated_total_pp": estimated_total_pp,
        "price_source": price_source,
        "price_source_detail": price_source_detail,
        "confidence": confidence,
        "price_sample_size": sample_size,
        "price_last_seen_at": price_seen_at,
        "category": category,
    }


def _estimated_price(row: sqlite3.Row) -> tuple[int | None, str | None, str | None, str | None, int | None, str | None]:
    override_amount = _as_float(row["override_price_amount"])
    override_currency = row["override_price_currency"]
    if override_amount is not None and override_amount > 0:
        if override_currency == "pp":
            return (
                round(override_amount),
                "manual_override",
                "manual_override_pp",
                row["override_confidence"] or "manual",
                None,
                None,
            )
        if override_currency == "krono":
            krono_price_pp = _as_int(row["krono_price_pp"])
            if krono_price_pp is not None and krono_price_pp > 0:
                return (
                    round(override_amount * krono_price_pp),
                    "manual_override",
                    "manual_override_krono",
                    row["override_confidence"] or "manual",
                    None,
                    None,
                )

    market_price_pp, market_field = _market_price(row)
    if market_price_pp is not None:
        sample_size = _as_int(row["market_sample_size"])
        return (
            market_price_pp,
            row["market_source"] or "market_prices",
            market_field,
            row["market_confidence"] or _sample_confidence(sample_size),
            sample_size,
            row["market_last_refresh_at"],
        )

    listing_price_pp = _as_int(row["listing_price_pp"])
    if listing_price_pp is not None and listing_price_pp > 0:
        sample_size = _as_int(row["listing_sample_size"])
        return (
            listing_price_pp,
            "recent_local_listings",
            "avg_price_pp",
            _sample_confidence(sample_size),
            sample_size,
            row["listing_last_seen_at"],
        )

    return None, None, None, None, None, None


def _market_price(row: sqlite3.Row) -> tuple[int | None, str | None]:
    for field in ("median_pp", "avg_pp", "p25_pp"):
        value = _as_int(row[field])
        if value is not None and value > 0:
            return value, field
    return None, None


def _decision_payload(row: sqlite3.Row) -> dict[str, Any] | None:
    if row["character_decision_status"] is not None:
        return {
            "decision_id": int(row["character_decision_id"]),
            "scope": "character",
            "status": row["character_decision_status"],
            "notes": row["character_decision_notes"],
            "created_at": row["character_decision_created_at"],
            "updated_at": row["character_decision_updated_at"],
        }
    if row["global_decision_status"] is not None:
        return {
            "decision_id": int(row["global_decision_id"]),
            "scope": "global",
            "status": row["global_decision_status"],
            "notes": row["global_decision_notes"],
            "created_at": row["global_decision_created_at"],
            "updated_at": row["global_decision_updated_at"],
        }
    return None


def _candidate_category(
    *,
    decision_status: str | None,
    has_price: bool,
    is_no_drop: bool,
    exclusion_reasons: list[str],
) -> str:
    if decision_status == "keep":
        return "keep"
    if decision_status == "ignore":
        return "ignored"
    if decision_status == "sell":
        return "sellable" if has_price else "unpriced"
    if is_no_drop:
        return "no_drop"
    if exclusion_reasons:
        return "excluded"
    if not has_price:
        return "unpriced"
    return "sellable"


def _categorize_items(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    categories: dict[str, list[dict[str, Any]]] = {category: [] for category in SELL_CANDIDATE_CATEGORIES}
    for item in items:
        categories[item["category"]].append(item)
    for category_items in categories.values():
        category_items.sort(key=_candidate_sort_key)
    return categories


def _candidate_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    value = item["estimated_total_pp"]
    return (
        -(value if value is not None else -1),
        str(item["character_name"]).lower(),
        str(item["item_name"]).lower(),
        int(item["item_id"]),
    )


def _global_item_rollups(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rollups: dict[tuple[str, int], dict[str, Any]] = {}

    for item in items:
        key = (str(item["server"]), int(item["item_id"]))
        rollup = rollups.get(key)
        if rollup is None:
            rollup = {
                "server": item["server"],
                "item_id": item["item_id"],
                "item_name": item["item_name"],
                "name": item["item_name"],
                "normalized_item_name": item["normalized_item_name"],
                "quantity": 0,
                "characters": [],
                "estimated_unit_price_pp": item["estimated_unit_price_pp"],
                "estimated_total_pp": 0 if item["estimated_unit_price_pp"] is not None else None,
                "price_source": item["price_source"],
                "price_source_detail": item["price_source_detail"],
                "confidence": item["confidence"],
                "categories": [],
            }
            rollups[key] = rollup

        rollup["quantity"] += int(item["quantity"])
        rollup["characters"].append(
            {
                "character_name": item["character_name"],
                "quantity": item["quantity"],
                "category": item["category"],
                "decision_status": item["decision_status"],
            }
        )
        if item["category"] not in rollup["categories"]:
            rollup["categories"].append(item["category"])
        if rollup["estimated_total_pp"] is not None and item["estimated_total_pp"] is not None:
            rollup["estimated_total_pp"] += int(item["estimated_total_pp"])
        elif rollup["estimated_total_pp"] is not None:
            rollup["estimated_total_pp"] = None

    for rollup in rollups.values():
        rollup["characters"].sort(key=lambda value: str(value["character_name"]).lower())
        rollup["categories"].sort()

    return sorted(
        rollups.values(),
        key=lambda item: (
            -(item["estimated_total_pp"] if item["estimated_total_pp"] is not None else -1),
            str(item["item_name"]).lower(),
            int(item["item_id"]),
        ),
    )


def _upsert_inventory_item_decision(
    connection: sqlite3.Connection,
    target: sqlite3.Row,
    *,
    server: str,
    scope: DecisionScope,
    character_name: str | None,
    status: DecisionStatus,
    notes: str | None,
) -> dict[str, Any]:
    scope_key = _scope_key(scope, character_name)
    connection.execute(
        """
        INSERT INTO inventory_item_decisions (
            server,
            scope,
            scope_key,
            character_name,
            item_id,
            item_name,
            normalized_item_name,
            status,
            notes,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(server, scope, scope_key, item_id) DO UPDATE SET
            item_name = excluded.item_name,
            normalized_item_name = excluded.normalized_item_name,
            status = excluded.status,
            notes = excluded.notes,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            server,
            scope,
            scope_key,
            character_name,
            int(target["item_id"]),
            target["name"],
            target["normalized_name"],
            status,
            notes,
        ),
    )
    return _fetch_inventory_item_decision_payload(connection, server, scope, scope_key, int(target["item_id"]))


def _delete_inventory_item_decision(
    connection: sqlite3.Connection,
    target: sqlite3.Row,
    *,
    server: str,
    scope: DecisionScope,
    character_name: str | None,
) -> dict[str, Any]:
    scope_key = _scope_key(scope, character_name)
    connection.execute(
        """
        DELETE FROM inventory_item_decisions
        WHERE server = ?
          AND scope = ?
          AND scope_key = ?
          AND item_id = ?
        """,
        (server, scope, scope_key, int(target["item_id"])),
    )

    return {
        "decision_id": None,
        "server": server,
        "scope": scope,
        "scope_key": scope_key,
        "character_name": character_name,
        "item_id": int(target["item_id"]),
        "item_name": target["name"],
        "normalized_item_name": target["normalized_name"],
        "status": None,
        "notes": None,
        "created_at": None,
        "updated_at": None,
    }


def _fetch_inventory_item_decision_payload(
    connection: sqlite3.Connection,
    server: str,
    scope: DecisionScope,
    scope_key: str,
    item_id: int,
) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT
            decision_id,
            server,
            scope,
            scope_key,
            character_name,
            item_id,
            item_name,
            normalized_item_name,
            status,
            notes,
            created_at,
            updated_at
        FROM inventory_item_decisions
        WHERE server = ?
          AND scope = ?
          AND scope_key = ?
          AND item_id = ?
        """,
        (server, scope, scope_key, item_id),
    ).fetchone()
    if row is None:
        raise sqlite3.DatabaseError("Inventory item decision write did not return a row")
    return _inventory_item_decision_payload(row)


def _inventory_item_decision_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "decision_id": int(row["decision_id"]),
        "server": row["server"],
        "scope": row["scope"],
        "scope_key": row["scope_key"],
        "character_name": row["character_name"],
        "item_id": int(row["item_id"]),
        "item_name": row["item_name"],
        "normalized_item_name": row["normalized_item_name"],
        "status": row["status"],
        "notes": row["notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _fetch_decision_target(connection: sqlite3.Connection, item_id: int) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT item_id, name, normalized_name
        FROM items
        WHERE item_id = ?
        """,
        (item_id,),
    ).fetchone()


def _fetch_character_or_404(connection: sqlite3.Connection, character_name: str) -> sqlite3.Row:
    normalized_name = character_name.strip().lower()
    if not normalized_name:
        raise HTTPException(status_code=400, detail="character_name must not be blank")

    row = connection.execute(
        """
        SELECT character_name, server
        FROM characters
        WHERE lower(character_name) = ?
        LIMIT 1
        """,
        (normalized_name,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Character not found")
    return row


def _default_exclusion_reasons(
    *,
    is_starter_item: bool,
    is_no_trade_import: bool,
    is_container: bool,
    is_consumable: bool,
) -> list[str]:
    reasons: list[str] = []
    if is_starter_item:
        reasons.append("starter")
    elif is_no_trade_import:
        reasons.append("no_trade_import")
    if is_container:
        reasons.append("container")
    if is_consumable:
        reasons.append("consumable")
    return reasons


def _is_excluded_consumable(normalized_name: str | None, item_type: str | None) -> bool:
    if item_type is not None and item_type.strip().lower() in INVENTORY_EXCLUDED_ITEM_TYPES:
        return True

    normalized = (normalized_name or "").strip().lower()
    if not normalized:
        return False
    if normalized in INVENTORY_EXCLUDED_NORMALIZED_NAMES:
        return True
    if normalized.endswith(" ration") or normalized.endswith(" rations"):
        return True
    return "water flask" in normalized or "fish rolls" in normalized


def _area_quantities(row: sqlite3.Row) -> dict[str, int]:
    area_quantities = {
        "carried": _as_int(row["carried_quantity"]) or 0,
        "bank": _as_int(row["bank_quantity"]) or 0,
        "shared_bank": _as_int(row["shared_bank_quantity"]) or 0,
    }
    return {area: quantity for area, quantity in area_quantities.items() if quantity > 0}


def _sorted_areas(value: Any) -> list[str]:
    areas = _csv_values(value)
    return sorted(areas, key=lambda area: AREA_ORDER.get(area, 99))


def _csv_values(value: Any) -> list[str]:
    if value is None:
        return []
    values: list[str] = []
    for raw in str(value).split(","):
        item = raw.strip()
        if item and item not in values:
            values.append(item)
    return values


def _is_no_trade_import(is_starter_item: bool, flags: Any) -> bool:
    tokens = _flag_tokens(flags)
    return bool(is_starter_item or "NO_TRADE_IMPORT" in tokens or "STARTER" in tokens)


def _flag_tokens(flags: Any) -> set[str]:
    if flags is None:
        return set()
    return {token.strip().upper() for token in str(flags).replace(";", ",").replace(" ", ",").split(",") if token.strip()}


def _scope_key(scope: DecisionScope, character_name: str | None) -> str:
    if scope == "global":
        return "*"
    if character_name is None:
        raise ValueError("character_name is required for character-scoped decisions")
    return character_name.strip().lower()


def _server_for_character(character: sqlite3.Row) -> str:
    server = _normalize_optional_server(character["server"])
    if server is None:
        raise HTTPException(status_code=400, detail="Character has no server")
    return server


def _normalize_required_server(server: str) -> str:
    normalized = server.strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="server must not be blank")
    return normalized


def _normalize_optional_server(server: Any) -> str | None:
    if server is None:
        return None
    normalized = str(server).strip().lower()
    return normalized or None


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


def _sample_confidence(sample_size: int | None) -> str:
    if sample_size is None:
        return "unknown"
    if sample_size >= 20:
        return "high"
    if sample_size >= 5:
        return "medium"
    if sample_size >= 1:
        return "low"
    return "none"


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request

from eqmarket.api.db import connect_readonly
from eqmarket.slot_masks import decode_lucy_slot_mask


InventoryArea = Literal["carried", "bank", "shared_bank", "all"]

DEFAULT_IMPORT_LIMIT = 20
NON_EQUIPMENT_INVENTORY_AREAS = ("carried", "bank", "shared_bank")
AREA_ORDER = {"carried": 0, "bank": 1, "shared_bank": 2}
DUPLICATE_EQUIPMENT_SLOTS = {"EAR", "WRIST", "FINGER"}

PAPERDOLL_SLOT_DEFINITIONS: tuple[tuple[str, str, int, str], ...] = (
    ("CHARM", "CHARM", 1, "Charm"),
    ("EAR_1", "EAR", 1, "Ear 1"),
    ("HEAD", "HEAD", 1, "Head"),
    ("FACE", "FACE", 1, "Face"),
    ("EAR_2", "EAR", 2, "Ear 2"),
    ("NECK", "NECK", 1, "Neck"),
    ("SHOULDERS", "SHOULDERS", 1, "Shoulders"),
    ("ARMS", "ARMS", 1, "Arms"),
    ("BACK", "BACK", 1, "Back"),
    ("WRIST_1", "WRIST", 1, "Wrist 1"),
    ("WRIST_2", "WRIST", 2, "Wrist 2"),
    ("RANGE", "RANGE", 1, "Range"),
    ("HANDS", "HANDS", 1, "Hands"),
    ("PRIMARY", "PRIMARY", 1, "Primary"),
    ("SECONDARY", "SECONDARY", 1, "Secondary"),
    ("FINGER_1", "FINGER", 1, "Finger 1"),
    ("FINGER_2", "FINGER", 2, "Finger 2"),
    ("CHEST", "CHEST", 1, "Chest"),
    ("LEGS", "LEGS", 1, "Legs"),
    ("FEET", "FEET", 1, "Feet"),
    ("WAIST", "WAIST", 1, "Waist"),
    ("POWER_SOURCE", "POWER_SOURCE", 1, "Power Source"),
    ("AMMO", "AMMO", 1, "Ammo"),
)
PAPERDOLL_SLOT_ORDER = tuple(slot_key for slot_key, _slot, _slot_index, _label in PAPERDOLL_SLOT_DEFINITIONS)

ITEM_COLUMNS = (
    "item_id",
    "name",
    "normalized_name",
    "item_type",
    "slot",
    "classes",
    "races",
    "ac",
    "hp",
    "mana",
    "endurance",
    "hp_regen",
    "mana_regen",
    "endurance_regen",
    "astr",
    "asta",
    "aagi",
    "adex",
    "awis",
    "aint",
    "acha",
    "heroic_str",
    "heroic_sta",
    "heroic_agi",
    "heroic_dex",
    "heroic_wis",
    "heroic_int",
    "heroic_cha",
    "sv_magic",
    "sv_fire",
    "sv_cold",
    "sv_poison",
    "sv_disease",
    "damage",
    "delay",
    "ratio",
    "haste",
    "required_level",
    "recommended_level",
    "icon_id",
    "flags",
    "source_primary",
    "last_imported_at",
)

STAT_FIELDS: tuple[tuple[str, str], ...] = (
    ("ac", "ac"),
    ("hp", "hp"),
    ("mana", "mana"),
    ("endurance", "endurance"),
    ("hp_regen", "hp_regen"),
    ("mana_regen", "mana_regen"),
    ("endurance_regen", "endurance_regen"),
    ("str", "astr"),
    ("sta", "asta"),
    ("agi", "aagi"),
    ("dex", "adex"),
    ("wis", "awis"),
    ("int", "aint"),
    ("cha", "acha"),
    ("heroic_str", "heroic_str"),
    ("heroic_sta", "heroic_sta"),
    ("heroic_agi", "heroic_agi"),
    ("heroic_dex", "heroic_dex"),
    ("heroic_wis", "heroic_wis"),
    ("heroic_int", "heroic_int"),
    ("heroic_cha", "heroic_cha"),
    ("sv_magic", "sv_magic"),
    ("sv_fire", "sv_fire"),
    ("sv_cold", "sv_cold"),
    ("sv_poison", "sv_poison"),
    ("sv_disease", "sv_disease"),
)

COMBAT_FIELDS = ("damage", "delay", "ratio", "haste")
LEVEL_FIELDS = ("required_level", "recommended_level")

router = APIRouter()


@router.get("/api/characters")
def list_characters(
    request: Request,
    server: str | None = Query(None, min_length=1),
) -> list[dict[str, Any]]:
    db_server = _normalize_optional_server(server)

    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        characters = _fetch_characters(connection, db_server)
        return [_character_payload(connection, character) for character in characters]


@router.get("/api/characters/{character_name}/equipment")
def character_equipment(
    character_name: str,
    request: Request,
) -> dict[str, Any]:
    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        character = _fetch_character_or_404(connection, character_name)
        db_server = _price_server_for_character(character)
        latest_import = _fetch_latest_import(connection, character["character_name"])
        rows = _fetch_equipment_rows(connection, character["character_name"], db_server)

    slots = _equipment_slots_payload(rows)
    return {
        "character_name": character["character_name"],
        "server": character["server"],
        "last_import": latest_import,
        "slot_order": list(slots.keys()),
        "slots": slots,
    }


@router.get("/api/characters/{character_name}/inventory")
def character_inventory(
    character_name: str,
    request: Request,
    area: InventoryArea = Query("all"),
    include_locations: bool = Query(False),
) -> dict[str, Any]:
    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        character = _fetch_character_or_404(connection, character_name)
        db_server = _price_server_for_character(character)
        latest_import = _fetch_latest_import(connection, character["character_name"])
        rows = _fetch_inventory_rows(connection, character["character_name"], db_server, area)

    items = _inventory_items_payload(rows, include_locations=include_locations)
    return {
        "character_name": character["character_name"],
        "server": character["server"],
        "area": area,
        "available_areas": list(NON_EQUIPMENT_INVENTORY_AREAS),
        "include_locations": include_locations,
        "last_import": latest_import,
        "item_count": len(items),
        "location_count": len(rows),
        "total_quantity": sum(int(item["quantity"]) for item in items),
        "items": items,
    }


@router.get("/api/characters/{character_name}/imports")
def character_imports(
    character_name: str,
    request: Request,
    limit: int = Query(DEFAULT_IMPORT_LIMIT, gt=0, le=100),
) -> dict[str, Any]:
    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        character = _fetch_character_or_404(connection, character_name)
        imports = _fetch_imports(connection, character["character_name"], limit)

    return {
        "character_name": character["character_name"],
        "server": character["server"],
        "limit": limit,
        "imports": imports,
    }


@router.get("/api/characters/{character_name}")
def character_detail(
    character_name: str,
    request: Request,
) -> dict[str, Any]:
    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        character = _fetch_character_or_404(connection, character_name)
        return _character_payload(connection, character, include_recent_imports=True)


def _fetch_characters(connection: sqlite3.Connection, db_server: str | None) -> list[sqlite3.Row]:
    params: list[Any] = []
    server_filter = ""
    if db_server is not None:
        server_filter = "WHERE lower(c.server) = ?"
        params.append(db_server)

    return connection.execute(
        f"""
        SELECT
            c.character_name,
            c.character_class,
            c.level,
            c.server,
            c.notes,
            c.created_at,
            c.updated_at
        FROM characters c
        {server_filter}
        ORDER BY lower(c.character_name)
        """,
        params,
    ).fetchall()


def _fetch_character_or_404(connection: sqlite3.Connection, character_name: str) -> sqlite3.Row:
    normalized_name = character_name.strip().lower()
    if not normalized_name:
        raise HTTPException(status_code=400, detail="character_name must not be blank")

    row = connection.execute(
        """
        SELECT
            character_name,
            character_class,
            level,
            server,
            notes,
            created_at,
            updated_at
        FROM characters
        WHERE lower(character_name) = ?
        LIMIT 1
        """,
        (normalized_name,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Character not found")
    return row


def _character_payload(
    connection: sqlite3.Connection,
    character: sqlite3.Row,
    *,
    include_recent_imports: bool = False,
) -> dict[str, Any]:
    character_name = character["character_name"]
    latest_import = _fetch_latest_import(connection, character_name)
    counters = _fetch_character_counters(connection, character_name, _price_server_for_character(character))

    payload: dict[str, Any] = {
        "character_name": character_name,
        "name": character_name,
        "server": character["server"],
        "character_class": character["character_class"],
        "level": _optional_int(character["level"]),
        "notes": character["notes"],
        "created_at": character["created_at"],
        "updated_at": character["updated_at"],
        "last_imported_at": latest_import["imported_at"] if latest_import is not None else None,
        "last_import": latest_import,
        "freshness": {
            "imported": latest_import is not None,
            "last_imported_at": latest_import["imported_at"] if latest_import is not None else None,
            "age_seconds": latest_import["age_seconds"] if latest_import is not None else None,
        },
        **counters,
    }
    if include_recent_imports:
        payload["recent_imports"] = _fetch_imports(connection, character_name, limit=5)
    return payload


def _fetch_character_counters(
    connection: sqlite3.Connection,
    character_name: str,
    db_server: str | None,
) -> dict[str, Any]:
    equipment_count = _fetch_scalar_count(
        connection,
        "SELECT COUNT(*) FROM character_equipment WHERE character_name = ?",
        (character_name,),
    )
    inventory_row_count = _fetch_scalar_count(
        connection,
        """
        SELECT COUNT(*)
        FROM character_inventory_items
        WHERE character_name = ?
          AND area IN ('carried', 'bank', 'shared_bank')
        """,
        (character_name,),
    )
    inventory_quantity_row = connection.execute(
        """
        SELECT COALESCE(SUM(quantity), 0) AS quantity
        FROM character_inventory_items
        WHERE character_name = ?
          AND area IN ('carried', 'bank', 'shared_bank')
        """,
        (character_name,),
    ).fetchone()
    starter_row = connection.execute(
        """
        SELECT COALESCE(SUM(is_starter_item), 0) AS starter_count
        FROM (
            SELECT is_starter_item
            FROM character_equipment
            WHERE character_name = ?
            UNION ALL
            SELECT is_starter_item
            FROM character_inventory_items
            WHERE character_name = ?
              AND area IN ('carried', 'bank', 'shared_bank')
        ) current_items
        """,
        (character_name, character_name),
    ).fetchone()

    distinct_rows = connection.execute(
        """
        SELECT DISTINCT current_items.item_id, i.source_primary, i.flags,
            COALESCE(NULLIF(mp.median_pp, 0), NULLIF(mp.avg_pp, 0), NULLIF(mp.p25_pp, 0)) AS market_price_pp
        FROM (
            SELECT item_id
            FROM character_equipment
            WHERE character_name = ?
              AND item_id IS NOT NULL
            UNION
            SELECT item_id
            FROM character_inventory_items
            WHERE character_name = ?
              AND area IN ('carried', 'bank', 'shared_bank')
              AND item_id IS NOT NULL
        ) current_items
        LEFT JOIN items i
            ON i.item_id = current_items.item_id
        LEFT JOIN market_prices mp
            ON mp.item_id = current_items.item_id
           AND lower(mp.server) = ?
        """,
        (character_name, character_name, db_server or ""),
    ).fetchall()

    distinct_item_count = len(distinct_rows)
    unenriched_item_count = sum(1 for row in distinct_rows if not _is_enriched(row["source_primary"]))
    unpriced_item_count = sum(1 for row in distinct_rows if row["market_price_pp"] is None)

    return {
        "equipment_item_count": equipment_count,
        "inventory_item_count": inventory_row_count,
        "inventory_quantity": int(inventory_quantity_row["quantity"]),
        "starter_item_count": int(starter_row["starter_count"]),
        "distinct_item_count": distinct_item_count,
        "unenriched_item_count": unenriched_item_count,
        "unpriced_item_count": unpriced_item_count,
    }


def _fetch_latest_import(connection: sqlite3.Connection, character_name: str) -> dict[str, Any] | None:
    row = connection.execute(
        f"""
        SELECT {_import_select_columns()}
        FROM inventory_imports
        WHERE character_name = ?
        ORDER BY datetime(imported_at) DESC, imported_at DESC, inventory_import_id DESC
        LIMIT 1
        """,
        (character_name,),
    ).fetchone()
    return _import_payload(row) if row is not None else None


def _fetch_imports(connection: sqlite3.Connection, character_name: str, limit: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        f"""
        SELECT {_import_select_columns()}
        FROM inventory_imports
        WHERE character_name = ?
        ORDER BY datetime(imported_at) DESC, imported_at DESC, inventory_import_id DESC
        LIMIT ?
        """,
        (character_name, limit),
    ).fetchall()
    return [_import_payload(row) for row in rows]


def _import_select_columns() -> str:
    return """
            inventory_import_id,
            character_name,
            server,
            source_file,
            source_hash,
            source_size_bytes,
            parser_version,
            rows_seen,
            rows_imported,
            equipment_items_imported,
            inventory_items_imported,
            starter_items_seen,
            empty_rows_skipped,
            status,
            error,
            imported_at,
            CASE
                WHEN julianday(imported_at) IS NULL THEN NULL
                ELSE CAST(MAX(0, (julianday('now') - julianday(imported_at)) * 86400) AS INTEGER)
            END AS age_seconds
    """


def _import_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "inventory_import_id": int(row["inventory_import_id"]),
        "character_name": row["character_name"],
        "server": row["server"],
        "source_file": row["source_file"],
        "source_hash": row["source_hash"],
        "source_size_bytes": _optional_int(row["source_size_bytes"]),
        "parser_version": row["parser_version"],
        "rows_seen": int(row["rows_seen"]),
        "rows_imported": int(row["rows_imported"]),
        "equipment_items_imported": int(row["equipment_items_imported"]),
        "inventory_items_imported": int(row["inventory_items_imported"]),
        "starter_items_seen": int(row["starter_items_seen"]),
        "empty_rows_skipped": int(row["empty_rows_skipped"]),
        "status": row["status"],
        "error": row["error"],
        "imported_at": row["imported_at"],
        "age_seconds": _optional_int(row["age_seconds"]),
    }


def _fetch_equipment_rows(
    connection: sqlite3.Connection,
    character_name: str,
    db_server: str | None,
) -> list[sqlite3.Row]:
    return connection.execute(
        f"""
        SELECT
            ce.slot AS equipment_slot,
            ce.slot_index AS equipment_slot_index,
            ce.item_id AS equipment_item_id,
            ce.item_name AS equipment_item_name,
            ce.raw_item_name AS equipment_raw_item_name,
            ce.normalized_item_name AS equipment_normalized_item_name,
            ce.raw_location AS equipment_raw_location,
            ce.quantity AS equipment_quantity,
            ce.slots AS equipment_slots,
            ce.is_starter_item AS equipment_is_starter_item,
            ce.is_augment AS equipment_is_augment,
            ce.augment_parent_location AS equipment_augment_parent_location,
            ce.ac AS equipment_ac,
            ce.hp AS equipment_hp,
            ce.mana AS equipment_mana,
            ce.endurance AS equipment_endurance,
            ce.hp_regen AS equipment_hp_regen,
            ce.mana_regen AS equipment_mana_regen,
            ce.endurance_regen AS equipment_endurance_regen,
            ce.astr AS equipment_astr,
            ce.asta AS equipment_asta,
            ce.aagi AS equipment_aagi,
            ce.adex AS equipment_adex,
            ce.awis AS equipment_awis,
            ce.aint AS equipment_aint,
            ce.acha AS equipment_acha,
            ce.heroic_str AS equipment_heroic_str,
            ce.heroic_sta AS equipment_heroic_sta,
            ce.heroic_agi AS equipment_heroic_agi,
            ce.heroic_dex AS equipment_heroic_dex,
            ce.heroic_wis AS equipment_heroic_wis,
            ce.heroic_int AS equipment_heroic_int,
            ce.heroic_cha AS equipment_heroic_cha,
            {_item_select_aliases()},
            {_price_select_aliases()}
        FROM character_equipment ce
        LEFT JOIN items i
            ON i.item_id = ce.item_id
        LEFT JOIN market_prices mp
            ON mp.item_id = ce.item_id
           AND lower(mp.server) = ?
        WHERE ce.character_name = ?
        ORDER BY ce.slot, ce.slot_index
        """,
        (db_server or "", character_name),
    ).fetchall()


def _equipment_slots_payload(rows: list[sqlite3.Row]) -> dict[str, Any]:
    slots: dict[str, Any] = {
        slot_key: {
            "slot_key": slot_key,
            "slot": slot,
            "slot_index": slot_index,
            "label": label,
            "item": None,
        }
        for slot_key, slot, slot_index, label in PAPERDOLL_SLOT_DEFINITIONS
    }

    for row in rows:
        slot = _normalize_slot_label(row["equipment_slot"])
        slot_index = _optional_int(row["equipment_slot_index"]) or 1
        slot_key = _equipment_slot_key(slot, slot_index)
        if slot_key not in slots:
            slots[slot_key] = {
                "slot_key": slot_key,
                "slot": slot,
                "slot_index": slot_index,
                "label": _equipment_slot_label(slot, slot_index),
                "item": None,
            }
        slots[slot_key]["item"] = _equipment_item_payload(row)

    return slots


def _equipment_item_payload(row: sqlite3.Row) -> dict[str, Any]:
    item_id = _optional_int(row["item_item_id"]) or _optional_int(row["equipment_item_id"])
    flags = row["item_flags"]
    is_starter_item = bool(row["equipment_is_starter_item"])
    slot_payload = _slot_payload(row["item_slot"] if row["item_slot"] is not None else row["equipment_slots"])
    price = _price_payload(row)

    return {
        "item_id": item_id,
        "name": row["item_name"] or row["equipment_item_name"] or row["equipment_raw_item_name"],
        "raw_item_name": row["equipment_raw_item_name"],
        "imported_name": row["equipment_item_name"],
        "normalized_name": row["item_normalized_name"] or row["equipment_normalized_item_name"],
        "icon_url": None,
        "icon_id": _optional_int(row["item_icon_id"]),
        "item_type": row["item_item_type"],
        **slot_payload,
        "classes": row["item_classes"],
        "races": row["item_races"],
        "flags": flags,
        "quantity": _optional_int(row["equipment_quantity"]) or 1,
        "raw_location": row["equipment_raw_location"],
        "stats": _stats_payload(row, fallback_prefix="equipment"),
        "combat": _combat_payload(row),
        "levels": _levels_payload(row),
        "source_primary": row["item_source_primary"],
        "last_imported_at": row["item_last_imported_at"],
        "enriched": _is_enriched(row["item_source_primary"]),
        "enrichment_status": _enrichment_status(row["item_source_primary"]),
        "is_starter_item": is_starter_item,
        "is_no_trade_import": _is_no_trade_import(is_starter_item, flags),
        "is_augment": bool(row["equipment_is_augment"]),
        "augment_parent_location": row["equipment_augment_parent_location"],
        "has_price": price["market_price_pp"] is not None,
        "price": price,
    }


def _fetch_inventory_rows(
    connection: sqlite3.Connection,
    character_name: str,
    db_server: str | None,
    area: InventoryArea,
) -> list[sqlite3.Row]:
    area_filter = "cii.area IN ('carried', 'bank', 'shared_bank')"
    params: list[Any] = [db_server or "", character_name]
    if area != "all":
        area_filter = "cii.area = ?"
        params.append(area)

    return connection.execute(
        f"""
        SELECT
            cii.inventory_item_id AS inventory_row_id,
            cii.area AS inventory_area,
            cii.raw_location AS inventory_raw_location,
            cii.parent_location AS inventory_parent_location,
            cii.location_index AS inventory_location_index,
            cii.location_slot_index AS inventory_location_slot_index,
            cii.item_id AS inventory_item_id,
            cii.item_name AS inventory_item_name,
            cii.raw_item_name AS inventory_raw_item_name,
            cii.normalized_item_name AS inventory_normalized_item_name,
            cii.quantity AS inventory_quantity,
            cii.slots AS inventory_slots,
            cii.is_container AS inventory_is_container,
            cii.is_starter_item AS inventory_is_starter_item,
            cii.is_augment AS inventory_is_augment,
            cii.augment_parent_location AS inventory_augment_parent_location,
            {_item_select_aliases()},
            {_price_select_aliases()}
        FROM character_inventory_items cii
        LEFT JOIN items i
            ON i.item_id = cii.item_id
        LEFT JOIN market_prices mp
            ON mp.item_id = cii.item_id
           AND lower(mp.server) = ?
        WHERE cii.character_name = ?
          AND {area_filter}
        ORDER BY
            CASE cii.area
                WHEN 'carried' THEN 0
                WHEN 'bank' THEN 1
                WHEN 'shared_bank' THEN 2
                ELSE 3
            END,
            cii.location_index,
            cii.raw_location,
            cii.inventory_item_id
        """,
        params,
    ).fetchall()


def _inventory_items_payload(rows: list[sqlite3.Row], *, include_locations: bool) -> list[dict[str, Any]]:
    items_by_id: dict[int, dict[str, Any]] = {}

    for row in rows:
        item_id = _optional_int(row["item_item_id"]) or int(row["inventory_item_id"])
        payload = items_by_id.get(item_id)
        if payload is None:
            item_payload = _inventory_item_payload(row)
            payload = {
                "item_id": item_id,
                "item_name": item_payload["name"],
                "name": item_payload["name"],
                "quantity": 0,
                "areas": [],
                "area_quantities": {},
                "raw_item_names": [],
                "is_starter_item": False,
                "is_no_trade_import": False,
                "is_container": False,
                "is_augment": False,
                "has_price": item_payload["has_price"],
                "enriched": item_payload["enriched"],
                "enrichment_status": item_payload["enrichment_status"],
                "locations": [] if include_locations else None,
                "item": item_payload,
            }
            items_by_id[item_id] = payload

        quantity = _optional_int(row["inventory_quantity"]) or 1
        area = row["inventory_area"]
        payload["quantity"] += quantity
        payload["area_quantities"][area] = payload["area_quantities"].get(area, 0) + quantity
        if area not in payload["areas"]:
            payload["areas"].append(area)

        raw_item_name = row["inventory_raw_item_name"]
        if raw_item_name and raw_item_name not in payload["raw_item_names"]:
            payload["raw_item_names"].append(raw_item_name)

        row_is_starter = bool(row["inventory_is_starter_item"])
        payload["is_starter_item"] = bool(payload["is_starter_item"] or row_is_starter)
        payload["is_no_trade_import"] = bool(
            payload["is_no_trade_import"] or _is_no_trade_import(row_is_starter, row["item_flags"])
        )
        payload["is_container"] = bool(payload["is_container"] or row["inventory_is_container"])
        payload["is_augment"] = bool(payload["is_augment"] or row["inventory_is_augment"])

        item_payload = payload["item"]
        item_payload["quantity"] = payload["quantity"]
        item_payload["is_starter_item"] = payload["is_starter_item"]
        item_payload["is_no_trade_import"] = payload["is_no_trade_import"]
        item_payload["is_container"] = payload["is_container"]
        item_payload["is_augment"] = payload["is_augment"]

        if include_locations:
            payload["locations"].append(_inventory_location_payload(row))

    for payload in items_by_id.values():
        payload["areas"].sort(key=lambda value: AREA_ORDER.get(value, 99))
        payload["area_quantities"] = {
            area: int(payload["area_quantities"][area])
            for area in sorted(payload["area_quantities"], key=lambda value: AREA_ORDER.get(value, 99))
        }
        payload["quantity"] = int(payload["quantity"])

    return sorted(
        items_by_id.values(),
        key=lambda item: (item["name"].lower() if item["name"] else "", item["item_id"]),
    )


def _inventory_item_payload(row: sqlite3.Row) -> dict[str, Any]:
    item_id = _optional_int(row["item_item_id"]) or int(row["inventory_item_id"])
    flags = row["item_flags"]
    is_starter_item = bool(row["inventory_is_starter_item"])
    price = _price_payload(row)

    return {
        "item_id": item_id,
        "name": row["item_name"] or row["inventory_item_name"] or row["inventory_raw_item_name"],
        "raw_item_name": row["inventory_raw_item_name"],
        "imported_name": row["inventory_item_name"],
        "normalized_name": row["item_normalized_name"] or row["inventory_normalized_item_name"],
        "icon_url": None,
        "icon_id": _optional_int(row["item_icon_id"]),
        "item_type": row["item_item_type"],
        **_slot_payload(row["item_slot"] if row["item_slot"] is not None else row["inventory_slots"]),
        "classes": row["item_classes"],
        "races": row["item_races"],
        "flags": flags,
        "quantity": 0,
        "stats": _stats_payload(row),
        "combat": _combat_payload(row),
        "levels": _levels_payload(row),
        "source_primary": row["item_source_primary"],
        "last_imported_at": row["item_last_imported_at"],
        "enriched": _is_enriched(row["item_source_primary"]),
        "enrichment_status": _enrichment_status(row["item_source_primary"]),
        "is_starter_item": is_starter_item,
        "is_no_trade_import": _is_no_trade_import(is_starter_item, flags),
        "is_container": bool(row["inventory_is_container"]),
        "is_augment": bool(row["inventory_is_augment"]),
        "augment_parent_location": row["inventory_augment_parent_location"],
        "has_price": price["market_price_pp"] is not None,
        "price": price,
    }


def _inventory_location_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "inventory_item_id": int(row["inventory_row_id"]),
        "area": row["inventory_area"],
        "raw_location": row["inventory_raw_location"],
        "parent_location": row["inventory_parent_location"],
        "location_index": _optional_int(row["inventory_location_index"]),
        "location_slot_index": _optional_int(row["inventory_location_slot_index"]),
        "quantity": _optional_int(row["inventory_quantity"]) or 1,
        "raw_item_name": row["inventory_raw_item_name"],
        "is_container": bool(row["inventory_is_container"]),
        "is_starter_item": bool(row["inventory_is_starter_item"]),
        "is_augment": bool(row["inventory_is_augment"]),
        "augment_parent_location": row["inventory_augment_parent_location"],
    }


def _item_select_aliases() -> str:
    return ",\n            ".join(f"i.{column} AS item_{column}" for column in ITEM_COLUMNS)


def _price_select_aliases() -> str:
    return """
            mp.median_pp AS price_median_pp,
            mp.p25_pp AS price_p25_pp,
            mp.p75_pp AS price_p75_pp,
            mp.avg_pp AS price_avg_pp,
            mp.min_pp AS price_min_pp,
            mp.max_pp AS price_max_pp,
            mp.sample_size AS price_sample_size,
            mp.confidence AS price_confidence,
            mp.last_refresh_at AS price_last_refresh_at,
            mp.source AS price_source,
            COALESCE(NULLIF(mp.median_pp, 0), NULLIF(mp.avg_pp, 0), NULLIF(mp.p25_pp, 0)) AS price_market_price_pp,
            CASE
                WHEN mp.median_pp IS NOT NULL AND mp.median_pp > 0 THEN 'median_pp'
                WHEN mp.avg_pp IS NOT NULL AND mp.avg_pp > 0 THEN 'avg_pp'
                WHEN mp.p25_pp IS NOT NULL AND mp.p25_pp > 0 THEN 'p25_pp'
                ELSE NULL
            END AS price_market_price_source
    """


def _slot_payload(raw_slot: Any) -> dict[str, Any]:
    decoded = decode_lucy_slot_mask(raw_slot)
    return {
        "slot": decoded.slot_display,
        "slot_mask": decoded.slot_mask,
        "slot_labels": list(decoded.slot_labels),
        "slot_display": decoded.slot_display,
    }


def _stats_payload(row: sqlite3.Row, fallback_prefix: str | None = None) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    for output_name, column_name in STAT_FIELDS:
        value = row[f"item_{column_name}"]
        if value is None and fallback_prefix is not None and _row_has_key(row, f"{fallback_prefix}_{column_name}"):
            value = row[f"{fallback_prefix}_{column_name}"]
        stats[output_name] = _optional_int(value)
    return stats


def _combat_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "damage": _optional_int(row["item_damage"]),
        "delay": _optional_int(row["item_delay"]),
        "ratio": _optional_float(row["item_ratio"]),
        "haste": _optional_int(row["item_haste"]),
    }


def _levels_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "required_level": _optional_int(row["item_required_level"]),
        "recommended_level": _optional_int(row["item_recommended_level"]),
    }


def _price_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "market_price_pp": _optional_int(row["price_market_price_pp"]),
        "market_price_source": row["price_market_price_source"],
        "median_pp": _optional_int(row["price_median_pp"]),
        "p25_pp": _optional_int(row["price_p25_pp"]),
        "p75_pp": _optional_int(row["price_p75_pp"]),
        "avg_pp": _optional_int(row["price_avg_pp"]),
        "min_pp": _optional_int(row["price_min_pp"]),
        "max_pp": _optional_int(row["price_max_pp"]),
        "sample_size": _optional_int(row["price_sample_size"]),
        "confidence": row["price_confidence"],
        "last_refresh_at": row["price_last_refresh_at"],
        "source": row["price_source"],
    }


def _fetch_scalar_count(connection: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> int:
    row = connection.execute(sql, params).fetchone()
    return int(row[0])


def _price_server_for_character(character: sqlite3.Row) -> str | None:
    server = character["server"]
    if server is None:
        return None
    normalized = str(server).strip().lower()
    return normalized or None


def _normalize_optional_server(server: str | None) -> str | None:
    if server is None:
        return None
    normalized = server.strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="server must not be blank")
    return normalized


def _normalize_slot_label(value: Any) -> str:
    normalized = str(value or "UNKNOWN").strip().upper().replace(" ", "_").replace("-", "_")
    return normalized or "UNKNOWN"


def _equipment_slot_key(slot: str, slot_index: int) -> str:
    if slot in DUPLICATE_EQUIPMENT_SLOTS or slot_index != 1:
        return f"{slot}_{slot_index}"
    return slot


def _equipment_slot_label(slot: str, slot_index: int) -> str:
    text = slot.replace("_", " ").title()
    if slot in DUPLICATE_EQUIPMENT_SLOTS or slot_index != 1:
        return f"{text} {slot_index}"
    return text


def _is_enriched(source_primary: Any) -> bool:
    if source_primary is None:
        return False
    return str(source_primary).strip().lower() not in {"", "inventory_dump"}


def _enrichment_status(source_primary: Any) -> str:
    if _is_enriched(source_primary):
        return "enriched"
    if source_primary is not None and str(source_primary).strip().lower() == "inventory_dump":
        return "inventory_stub"
    return "unknown"


def _is_no_trade_import(is_starter_item: bool, flags: Any) -> bool:
    tokens = _flag_tokens(flags)
    return bool(is_starter_item or "NO_TRADE_IMPORT" in tokens or "STARTER" in tokens)


def _flag_tokens(flags: Any) -> set[str]:
    if flags is None:
        return set()
    return {token.strip().upper() for token in str(flags).replace(";", ",").replace(" ", ",").split(",") if token.strip()}


def _row_has_key(row: sqlite3.Row, key: str) -> bool:
    return key in row.keys()


def _connect_or_503(db_path: str | Path) -> sqlite3.Connection:
    try:
        return connect_readonly(db_path)
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"SQLite database is not readable: {exc}") from exc


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)

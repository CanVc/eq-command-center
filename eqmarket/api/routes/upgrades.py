from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request

from eqmarket.api.db import connect_readonly
from eqmarket.slot_masks import KNOWN_LUCY_SLOT_LABEL_SET, decode_lucy_slot_mask


UpgradeSourceFilter = Literal["owned", "market", "all"]
UpgradeProfile = Literal["auto", "tank", "monk", "sk"]

DEFAULT_LIMIT = 50
DEFAULT_LOCAL_LISTING_MAX_AGE_DAYS = 30
MARKET_CANDIDATE_SCAN_LIMIT = 2000
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

STAT_FIELDS: tuple[str, ...] = (
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
)
RESIST_FIELDS = ("sv_magic", "sv_fire", "sv_cold", "sv_poison", "sv_disease")
BASE_STAT_FIELDS = ("astr", "asta", "aagi", "adex", "awis", "aint", "acha")
COMBAT_FIELDS = ("damage", "delay", "ratio", "haste")
LEVEL_FIELDS = ("required_level", "recommended_level")

PROFILE_WEIGHTS: dict[str, dict[str, float]] = {
    "tank": {
        "ac": 4.0,
        "hp": 0.20,
        "mana": 0.03,
        "endurance": 0.05,
        "resists_total": 0.10,
        "base_stats_total": 0.05,
        "ratio": 250.0,
    },
    "sk": {
        "ac": 3.5,
        "hp": 0.18,
        "mana": 0.08,
        "endurance": 0.05,
        "resists_total": 0.10,
        "base_stats_total": 0.06,
        "ratio": 300.0,
    },
    "monk": {
        "ac": 2.5,
        "hp": 0.14,
        "mana": 0.0,
        "endurance": 0.08,
        "resists_total": 0.08,
        "base_stats_total": 0.06,
        "ratio": 700.0,
    },
}

CLASS_CODE_BY_NAME = {
    "warrior": "WAR",
    "war": "WAR",
    "cleric": "CLR",
    "clr": "CLR",
    "paladin": "PAL",
    "pal": "PAL",
    "ranger": "RNG",
    "rng": "RNG",
    "shadow knight": "SHD",
    "shadowknight": "SHD",
    "sk": "SHD",
    "shd": "SHD",
    "druid": "DRU",
    "dru": "DRU",
    "monk": "MNK",
    "mnk": "MNK",
    "bard": "BRD",
    "brd": "BRD",
    "rogue": "ROG",
    "rog": "ROG",
    "shaman": "SHM",
    "shm": "SHM",
    "necromancer": "NEC",
    "nec": "NEC",
    "wizard": "WIZ",
    "wiz": "WIZ",
    "magician": "MAG",
    "mage": "MAG",
    "mag": "MAG",
    "enchanter": "ENC",
    "enc": "ENC",
    "beastlord": "BST",
    "bst": "BST",
    "berserker": "BER",
    "ber": "BER",
}

CLASS_ALIASES = {
    "WAR": {"WAR", "WARRIOR"},
    "CLR": {"CLR", "CLERIC"},
    "PAL": {"PAL", "PALADIN"},
    "RNG": {"RNG", "RANGER"},
    "SHD": {"SHD", "SK", "SHADOWKNIGHT", "SHADOW_KNIGHT", "SHADOW KNIGHT"},
    "DRU": {"DRU", "DRUID"},
    "MNK": {"MNK", "MONK"},
    "BRD": {"BRD", "BARD"},
    "ROG": {"ROG", "ROGUE"},
    "SHM": {"SHM", "SHAMAN"},
    "NEC": {"NEC", "NECROMANCER"},
    "WIZ": {"WIZ", "WIZARD"},
    "MAG": {"MAG", "MAGE", "MAGICIAN"},
    "ENC": {"ENC", "ENCHANTER"},
    "BST": {"BST", "BEASTLORD", "BEAST LORD"},
    "BER": {"BER", "BERSERKER"},
}

CLASS_BIT_BY_CODE = {
    "WAR": 1,
    "CLR": 2,
    "PAL": 4,
    "RNG": 8,
    "SHD": 16,
    "DRU": 32,
    "MNK": 64,
    "BRD": 128,
    "ROG": 256,
    "SHM": 512,
    "NEC": 1024,
    "WIZ": 2048,
    "MAG": 4096,
    "ENC": 8192,
    "BST": 16384,
    "BER": 32768,
}

UNKNOWN_CLASS_TOKENS = {"", "UNKNOWN", "CLASSUNKNOWN", "N/A", "NA", "NONE", "NULL", "?"}

router = APIRouter()


@router.get("/api/characters/{character_name}/upgrades")
def character_upgrades(
    character_name: str,
    request: Request,
    slot: str | None = Query(None, min_length=1),
    max_price_pp: int | None = Query(None, ge=0),
    source: UpgradeSourceFilter = Query("all"),
    profile: UpgradeProfile = Query("auto"),
    limit: int = Query(DEFAULT_LIMIT, gt=0, le=200),
    local_listing_max_age_days: int = Query(DEFAULT_LOCAL_LISTING_MAX_AGE_DAYS, ge=1, le=3650),
) -> dict[str, Any]:
    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        character = _fetch_character_or_404(connection, character_name)
        db_server = _normalize_optional_server(character["server"])
        slot_targets = _slot_targets(slot)
        equipment = _current_equipment_by_slot(connection, character["character_name"], db_server)
        raw_candidates = _fetch_raw_candidates(
            connection,
            character_name=character["character_name"],
            server=db_server,
            source=source,
            local_listing_max_age_days=local_listing_max_age_days,
        )

    character_class = character["character_class"]
    resolved_profile = _resolve_profile(profile, character_class)
    candidates = _upgrade_candidates(
        raw_candidates,
        equipment=equipment,
        slot_targets=slot_targets,
        character_class=character_class,
        resolved_profile=resolved_profile,
        max_price_pp=max_price_pp,
    )
    candidates.sort(key=_candidate_sort_key)
    candidates = candidates[:limit]

    return {
        "character_name": character["character_name"],
        "server": character["server"],
        "character_class": character_class,
        "profile": profile,
        "resolved_profile": resolved_profile,
        "source": source,
        "slot": _normalize_optional_slot_filter(slot),
        "max_price_pp": max_price_pp,
        "local_listing_max_age_days": local_listing_max_age_days,
        "limit": limit,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def _fetch_raw_candidates(
    connection: sqlite3.Connection,
    *,
    character_name: str,
    server: str | None,
    source: str,
    local_listing_max_age_days: int,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    owned_item_ids: set[int] = set()

    if source in {"owned", "all"}:
        owned_rows = _fetch_owned_rows(connection, character_name)
        for row in owned_rows:
            candidate = _candidate_from_owned_row(row)
            candidates.append(candidate)
            owned_item_ids.add(int(candidate["item"]["item_id"]))

    if source in {"market", "all"} and server is not None:
        listing_rows = _fetch_listing_rows(connection, server, local_listing_max_age_days)
        for row in listing_rows:
            candidate = _candidate_from_listing_row(row)
            candidates.append(candidate)
            owned_item_ids.add(int(candidate["item"]["item_id"]))

        market_rows = _fetch_market_rows(connection, server)
        for row in market_rows:
            item_id = int(row["item_id"])
            if source == "all" and item_id in owned_item_ids:
                continue
            candidates.append(_candidate_from_market_row(row))

    return candidates


def _fetch_owned_rows(connection: sqlite3.Connection, character_name: str) -> list[sqlite3.Row]:
    return connection.execute(
        f"""
        WITH owned_groups AS (
            SELECT
                cii.character_name,
                lower(cii.server) AS server,
                cii.item_id,
                COALESCE(NULLIF(i.name, ''), cii.item_name) AS candidate_name,
                COALESCE(NULLIF(i.normalized_name, ''), cii.normalized_item_name) AS normalized_name,
                SUM(cii.quantity) AS quantity,
                SUM(CASE WHEN cii.area = 'carried' THEN cii.quantity ELSE 0 END) AS carried_quantity,
                SUM(CASE WHEN cii.area = 'bank' THEN cii.quantity ELSE 0 END) AS bank_quantity,
                SUM(CASE WHEN cii.area = 'shared_bank' THEN cii.quantity ELSE 0 END) AS shared_bank_quantity,
                GROUP_CONCAT(DISTINCT cii.area) AS areas_csv,
                MAX(COALESCE(cii.is_starter_item, 0)) AS is_starter_item,
                MAX(COALESCE(cii.is_container, 0)) AS is_container,
                MAX(COALESCE(cii.is_augment, 0)) AS is_augment,
                COALESCE(NULLIF(i.slot, ''), MAX(NULLIF(cii.slots, ''))) AS candidate_slot,
                i.item_type,
                i.classes,
                i.races,
                i.icon_id,
                i.flags,
                i.source_primary,
                i.last_imported_at,
                {_item_stats_select("i")},
                {_item_combat_select("i")},
                {_item_level_select("i")}
            FROM character_inventory_items cii
            LEFT JOIN items i
                ON i.item_id = cii.item_id
            WHERE lower(cii.character_name) = ?
              AND cii.area IN ('carried', 'bank', 'shared_bank')
            GROUP BY cii.character_name, lower(cii.server), cii.item_id
        )
        SELECT
            owned_groups.*,
            mp.median_pp,
            mp.p25_pp,
            mp.p75_pp,
            mp.avg_pp,
            mp.min_pp,
            mp.max_pp,
            mp.sample_size,
            mp.confidence,
            mp.last_refresh_at,
            mp.source AS market_source,
            cd.status AS character_decision_status,
            gd.status AS global_decision_status
        FROM owned_groups
        LEFT JOIN market_prices mp
            ON mp.item_id = owned_groups.item_id
           AND lower(mp.server) = owned_groups.server
        LEFT JOIN inventory_item_decisions cd
            ON cd.server = owned_groups.server
           AND cd.scope = 'character'
           AND cd.scope_key = lower(owned_groups.character_name)
           AND cd.item_id = owned_groups.item_id
        LEFT JOIN inventory_item_decisions gd
            ON gd.server = owned_groups.server
           AND gd.scope = 'global'
           AND gd.scope_key = '*'
           AND gd.item_id = owned_groups.item_id
        ORDER BY lower(owned_groups.candidate_name), owned_groups.item_id
        """,
        (character_name.strip().lower(),),
    ).fetchall()


def _fetch_listing_rows(
    connection: sqlite3.Connection,
    server: str,
    local_listing_max_age_days: int,
) -> list[sqlite3.Row]:
    return connection.execute(
        f"""
        WITH active_listings AS (
            SELECT
                ml.*,
                ROW_NUMBER() OVER (
                    PARTITION BY ml.item_id, lower(ml.server)
                    ORDER BY ml.price_pp ASC, datetime(ml.timestamp) DESC, ml.listing_id DESC
                ) AS listing_rank
            FROM market_listings ml
            LEFT JOIN market_listing_reviews mlr
                ON mlr.listing_id = ml.listing_id
            WHERE lower(ml.server) = ?
              AND ml.item_id IS NOT NULL
              AND ml.price_pp IS NOT NULL
              AND ml.price_pp > 0
              AND COALESCE(mlr.status, 'active') = 'active'
              AND datetime(ml.timestamp) >= datetime('now', ?)
        )
        SELECT
            al.listing_id,
            al.server,
            al.timestamp,
            al.seller,
            al.price_raw,
            al.price_pp,
            al.confidence AS listing_confidence,
            i.item_id,
            i.name AS candidate_name,
            i.normalized_name,
            i.item_type,
            i.slot AS candidate_slot,
            i.classes,
            i.races,
            i.icon_id,
            i.flags,
            i.source_primary,
            i.last_imported_at,
            {_item_stats_select("i")},
            {_item_combat_select("i")},
            {_item_level_select("i")},
            mp.median_pp,
            mp.p25_pp,
            mp.p75_pp,
            mp.avg_pp,
            mp.min_pp,
            mp.max_pp,
            mp.sample_size,
            mp.confidence,
            mp.last_refresh_at,
            mp.source AS market_source
        FROM active_listings al
        JOIN items i
            ON i.item_id = al.item_id
        LEFT JOIN market_prices mp
            ON mp.item_id = al.item_id
           AND lower(mp.server) = lower(al.server)
        WHERE al.listing_rank = 1
        ORDER BY al.price_pp ASC, lower(i.name)
        LIMIT {MARKET_CANDIDATE_SCAN_LIMIT}
        """,
        (server, f"-{local_listing_max_age_days} days"),
    ).fetchall()


def _fetch_market_rows(connection: sqlite3.Connection, server: str) -> list[sqlite3.Row]:
    return connection.execute(
        f"""
        SELECT
            i.item_id,
            i.name AS candidate_name,
            i.normalized_name,
            i.item_type,
            i.slot AS candidate_slot,
            i.classes,
            i.races,
            i.icon_id,
            i.flags,
            i.source_primary,
            i.last_imported_at,
            {_item_stats_select("i")},
            {_item_combat_select("i")},
            {_item_level_select("i")},
            mp.median_pp,
            mp.p25_pp,
            mp.p75_pp,
            mp.avg_pp,
            mp.min_pp,
            mp.max_pp,
            mp.sample_size,
            mp.confidence,
            mp.last_refresh_at,
            mp.source AS market_source
        FROM market_prices mp
        JOIN items i
            ON i.item_id = mp.item_id
        WHERE lower(mp.server) = ?
          AND COALESCE(NULLIF(mp.median_pp, 0), NULLIF(mp.avg_pp, 0), NULLIF(mp.p25_pp, 0)) IS NOT NULL
        ORDER BY COALESCE(NULLIF(mp.median_pp, 0), NULLIF(mp.avg_pp, 0), NULLIF(mp.p25_pp, 0)) DESC, lower(i.name)
        LIMIT {MARKET_CANDIDATE_SCAN_LIMIT}
        """,
        (server,),
    ).fetchall()


def _current_equipment_by_slot(
    connection: sqlite3.Connection,
    character_name: str,
    server: str | None,
) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        f"""
        SELECT
            ce.slot AS equipment_slot,
            ce.slot_index AS equipment_slot_index,
            ce.item_id AS equipment_item_id,
            ce.item_name AS equipment_item_name,
            ce.raw_item_name AS equipment_raw_item_name,
            ce.normalized_item_name AS equipment_normalized_name,
            ce.slots AS equipment_slots,
            i.item_id,
            i.name AS item_name,
            i.normalized_name,
            i.item_type,
            i.slot AS item_slot,
            i.classes,
            i.races,
            i.icon_id,
            i.flags,
            i.source_primary,
            i.last_imported_at,
            {_item_stats_select("i")},
            {_item_combat_select("i")},
            {_item_level_select("i")},
            {_equipment_stat_select("ce")},
            mp.median_pp,
            mp.p25_pp,
            mp.p75_pp,
            mp.avg_pp,
            mp.min_pp,
            mp.max_pp,
            mp.sample_size,
            mp.confidence,
            mp.last_refresh_at,
            mp.source AS market_source
        FROM character_equipment ce
        LEFT JOIN items i
            ON i.item_id = ce.item_id
        LEFT JOIN market_prices mp
            ON mp.item_id = ce.item_id
           AND lower(mp.server) = ?
        WHERE lower(ce.character_name) = ?
        """,
        (server or "", character_name.strip().lower()),
    ).fetchall()

    slots = {
        slot_key: {
            "slot_key": slot_key,
            "slot": slot_name,
            "slot_index": slot_index,
            "label": label,
            "item": None,
        }
        for slot_key, slot_name, slot_index, label in PAPERDOLL_SLOT_DEFINITIONS
    }
    for row in rows:
        slot_name = _normalize_slot(row["equipment_slot"])
        slot_index = _as_int(row["equipment_slot_index"]) or 1
        slot_key = _slot_key(slot_name, slot_index)
        slots.setdefault(
            slot_key,
            {
                "slot_key": slot_key,
                "slot": slot_name,
                "slot_index": slot_index,
                "label": _slot_label(slot_name, slot_index),
                "item": None,
            },
        )
        slots[slot_key]["item"] = _equipment_item_from_row(row)
    return slots


def _upgrade_candidates(
    raw_candidates: list[dict[str, Any]],
    *,
    equipment: dict[str, dict[str, Any]],
    slot_targets: list[dict[str, Any]],
    character_class: str | None,
    resolved_profile: str,
    max_price_pp: int | None,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int, str]] = set()

    for raw_candidate in raw_candidates:
        decision_status = raw_candidate.get("decision_status")
        if decision_status == "ignore":
            continue
        if raw_candidate.get("is_container") or raw_candidate.get("is_augment"):
            continue
        if raw_candidate["source"] != "owned" and _is_no_drop(raw_candidate["item"]["flags"]):
            continue
        if not _class_compatible(raw_candidate["item"]["classes"], character_class):
            continue

        cost_pp = raw_candidate["cost_pp"]
        if max_price_pp is not None and cost_pp is not None and cost_pp > max_price_pp:
            continue

        candidate_slots = set(raw_candidate["item"]["slot_labels"])
        if not candidate_slots:
            continue

        for slot_target in slot_targets:
            if slot_target["slot"] not in candidate_slots:
                continue

            current_slot = equipment.get(slot_target["slot_key"], slot_target)
            current_item = current_slot.get("item")
            deltas = _deltas(raw_candidate["item"], current_item)
            score = _score(deltas, resolved_profile)
            if score <= 0:
                continue

            key = (slot_target["slot_key"], int(raw_candidate["item"]["item_id"]), raw_candidate["source"])
            if key in seen_keys:
                continue
            seen_keys.add(key)

            candidates.append(
                {
                    "slot_key": slot_target["slot_key"],
                    "slot": slot_target["slot"],
                    "slot_label": slot_target["label"],
                    "current_item": _current_item_payload(current_item),
                    "candidate": raw_candidate["item"],
                    "source": raw_candidate["source"],
                    "source_detail": raw_candidate["source_detail"],
                    "quantity": raw_candidate.get("quantity"),
                    "areas": raw_candidate.get("areas", []),
                    "area_quantities": raw_candidate.get("area_quantities", {}),
                    "listing": raw_candidate.get("listing"),
                    "decision_status": decision_status,
                    "cost_pp": cost_pp,
                    "market_price_pp": raw_candidate["market_price_pp"],
                    "price_source": raw_candidate["price_source"],
                    "confidence": raw_candidate["confidence"],
                    "deltas": deltas,
                    "score": score,
                }
            )

    return candidates


def _candidate_from_owned_row(row: sqlite3.Row) -> dict[str, Any]:
    price = _market_price(row)
    decision_status = row["character_decision_status"] or row["global_decision_status"]
    return {
        "source": "owned",
        "source_detail": "inventory",
        "quantity": _as_int(row["quantity"]) or 0,
        "areas": _sorted_areas(row["areas_csv"]),
        "area_quantities": _area_quantities(row),
        "is_container": bool(row["is_container"]),
        "is_augment": bool(row["is_augment"]),
        "decision_status": decision_status,
        "cost_pp": 0,
        "market_price_pp": price["market_price_pp"],
        "price_source": price["market_price_source"],
        "confidence": price["confidence"],
        "item": _candidate_item_from_row(row),
    }


def _candidate_from_listing_row(row: sqlite3.Row) -> dict[str, Any]:
    price = _market_price(row)
    listing_price = _as_int(row["price_pp"])
    return {
        "source": "local_listing",
        "source_detail": "eq_log",
        "quantity": 1,
        "areas": [],
        "area_quantities": {},
        "is_container": False,
        "is_augment": False,
        "decision_status": None,
        "cost_pp": listing_price,
        "market_price_pp": price["market_price_pp"],
        "price_source": "local_listing",
        "confidence": row["listing_confidence"] or price["confidence"],
        "listing": {
            "listing_id": int(row["listing_id"]),
            "timestamp": row["timestamp"],
            "seller": row["seller"],
            "price_raw": row["price_raw"],
            "price_pp": listing_price,
        },
        "item": _candidate_item_from_row(row),
    }


def _candidate_from_market_row(row: sqlite3.Row) -> dict[str, Any]:
    price = _market_price(row)
    return {
        "source": "market_price",
        "source_detail": row["market_source"] or "market_prices",
        "quantity": None,
        "areas": [],
        "area_quantities": {},
        "is_container": False,
        "is_augment": False,
        "decision_status": None,
        "cost_pp": price["market_price_pp"],
        "market_price_pp": price["market_price_pp"],
        "price_source": price["market_price_source"],
        "confidence": price["confidence"],
        "item": _candidate_item_from_row(row),
    }


def _candidate_item_from_row(row: sqlite3.Row) -> dict[str, Any]:
    slot_payload = _slot_payload(row["candidate_slot"])
    return {
        "item_id": int(row["item_id"]),
        "name": row["candidate_name"],
        "normalized_name": row["normalized_name"],
        "icon_url": None,
        "icon_id": _as_int(row["icon_id"]),
        "item_type": row["item_type"],
        **slot_payload,
        "classes": row["classes"],
        "races": row["races"],
        "flags": row["flags"],
        "stats": _stats_payload(row),
        "combat": _combat_payload(row),
        "levels": _levels_payload(row),
        "source_primary": row["source_primary"],
        "last_imported_at": row["last_imported_at"],
        "price": _market_price(row),
    }


def _equipment_item_from_row(row: sqlite3.Row) -> dict[str, Any] | None:
    item_id = _as_int(row["item_id"]) or _as_int(row["equipment_item_id"])
    if item_id is None:
        return None
    slot_payload = _slot_payload(row["item_slot"] if row["item_slot"] is not None else row["equipment_slots"])
    return {
        "item_id": item_id,
        "name": row["item_name"] or row["equipment_item_name"] or row["equipment_raw_item_name"],
        "normalized_name": row["normalized_name"] or row["equipment_normalized_name"],
        "icon_url": None,
        "icon_id": _as_int(row["icon_id"]),
        "item_type": row["item_type"],
        **slot_payload,
        "classes": row["classes"],
        "races": row["races"],
        "flags": row["flags"],
        "stats": _stats_payload(row, fallback_prefix="equipment"),
        "combat": _combat_payload(row),
        "levels": _levels_payload(row),
        "source_primary": row["source_primary"],
        "last_imported_at": row["last_imported_at"],
        "price": _market_price(row),
    }


def _current_item_payload(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "item_id": item["item_id"],
        "name": item["name"],
        "stats": item["stats"],
        "combat": item["combat"],
        "price": item["price"],
    }


def _deltas(candidate: dict[str, Any], current: dict[str, Any] | None) -> dict[str, Any]:
    current_stats = current["stats"] if current is not None else {}
    candidate_stats = candidate["stats"]
    stats = {
        _stat_output_name(field): _none_as_zero(candidate_stats.get(_stat_output_name(field)))
        - _none_as_zero(current_stats.get(_stat_output_name(field)))
        for field in STAT_FIELDS
    }
    resists_total = sum(stats[_stat_output_name(field)] for field in RESIST_FIELDS)
    base_stats_total = sum(stats[_stat_output_name(field)] for field in BASE_STAT_FIELDS)

    current_combat = current["combat"] if current is not None else {}
    candidate_ratio = _effective_ratio(candidate["combat"])
    current_ratio = _effective_ratio(current_combat)
    ratio_delta = None
    if candidate_ratio is not None or current_ratio is not None:
        ratio_delta = (candidate_ratio or 0.0) - (current_ratio or 0.0)

    return {
        **stats,
        "resists_total": resists_total,
        "base_stats_total": base_stats_total,
        "damage": _none_as_zero(candidate["combat"].get("damage")) - _none_as_zero(current_combat.get("damage")),
        "delay": _none_as_zero(candidate["combat"].get("delay")) - _none_as_zero(current_combat.get("delay")),
        "ratio": round(ratio_delta, 4) if ratio_delta is not None else None,
        "haste": _none_as_zero(candidate["combat"].get("haste")) - _none_as_zero(current_combat.get("haste")),
    }


def _score(deltas: dict[str, Any], profile: str) -> float:
    weights = PROFILE_WEIGHTS[profile]
    score = 0.0
    for key, weight in weights.items():
        if key == "ratio":
            ratio = deltas.get("ratio")
            if ratio is not None and ratio > 0:
                score += ratio * weight
            continue
        value = deltas.get(key)
        if value is not None and value > 0:
            score += value * weight
    return round(score, 2)


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    source_rank = {"owned": 0, "local_listing": 1, "market_price": 2}.get(candidate["source"], 9)
    cost = candidate["cost_pp"]
    return (
        -float(candidate["score"]),
        source_rank,
        cost if cost is not None else 10**12,
        str(candidate["candidate"]["name"]).lower(),
        int(candidate["candidate"]["item_id"]),
        str(candidate["slot_key"]),
    )


def _slot_targets(slot: str | None) -> list[dict[str, Any]]:
    normalized = _normalize_optional_slot_filter(slot)
    definitions = [
        {"slot_key": slot_key, "slot": slot_name, "slot_index": slot_index, "label": label}
        for slot_key, slot_name, slot_index, label in PAPERDOLL_SLOT_DEFINITIONS
    ]
    if normalized is None:
        return definitions

    key_matches = [target for target in definitions if target["slot_key"] == normalized]
    if key_matches:
        return key_matches

    if normalized in KNOWN_LUCY_SLOT_LABEL_SET:
        return [target for target in definitions if target["slot"] == normalized]

    raise HTTPException(status_code=400, detail=f"Unknown equipment slot: {slot}")


def _normalize_optional_slot_filter(slot: str | None) -> str | None:
    if slot is None:
        return None
    normalized = _normalize_slot(slot)
    return normalized or None


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
    for column_name in STAT_FIELDS:
        value = row[column_name] if _row_has_key(row, column_name) else None
        if value is None and fallback_prefix is not None and _row_has_key(row, f"{fallback_prefix}_{column_name}"):
            value = row[f"{fallback_prefix}_{column_name}"]
        stats[_stat_output_name(column_name)] = _as_int(value)
    return stats


def _combat_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "damage": _as_int(row["damage"]),
        "delay": _as_int(row["delay"]),
        "ratio": _as_float(row["ratio"]),
        "haste": _as_int(row["haste"]),
    }


def _levels_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "required_level": _as_int(row["required_level"]),
        "recommended_level": _as_int(row["recommended_level"]),
    }


def _market_price(row: sqlite3.Row) -> dict[str, Any]:
    market_price_pp: int | None = None
    market_price_source: str | None = None
    for field in ("median_pp", "avg_pp", "p25_pp"):
        value = _as_int(row[field])
        if value is not None and value > 0:
            market_price_pp = value
            market_price_source = field
            break
    return {
        "market_price_pp": market_price_pp,
        "market_price_source": market_price_source,
        "median_pp": _as_int(row["median_pp"]),
        "p25_pp": _as_int(row["p25_pp"]),
        "p75_pp": _as_int(row["p75_pp"]),
        "avg_pp": _as_int(row["avg_pp"]),
        "min_pp": _as_int(row["min_pp"]),
        "max_pp": _as_int(row["max_pp"]),
        "sample_size": _as_int(row["sample_size"]),
        "confidence": row["confidence"],
        "last_refresh_at": row["last_refresh_at"],
        "source": row["market_source"],
    }


def _item_stats_select(table_alias: str) -> str:
    return ",\n                ".join(f"{table_alias}.{field} AS {field}" for field in STAT_FIELDS)


def _item_combat_select(table_alias: str) -> str:
    return ",\n                ".join(f"{table_alias}.{field} AS {field}" for field in COMBAT_FIELDS)


def _item_level_select(table_alias: str) -> str:
    return ",\n                ".join(f"{table_alias}.{field} AS {field}" for field in LEVEL_FIELDS)


def _equipment_stat_select(table_alias: str) -> str:
    fields = [
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
    ]
    return ",\n            ".join(f"{table_alias}.{field} AS equipment_{field}" for field in fields)


def _resolve_profile(profile: str, character_class: str | None) -> str:
    if profile != "auto":
        return profile

    class_code = _character_class_code(character_class)
    if class_code == "MNK":
        return "monk"
    if class_code == "SHD":
        return "sk"
    return "tank"


def _class_compatible(item_classes: Any, character_class: str | None) -> bool:
    text = "" if item_classes is None else str(item_classes).strip()
    if not text:
        return True
    if "ALL" in _class_tokens(text):
        return True

    class_code = _character_class_code(character_class)
    if class_code is None:
        return True

    class_mask = _coerce_non_negative_int(text)
    if class_mask is not None:
        class_bit = CLASS_BIT_BY_CODE.get(class_code)
        return class_bit is None or bool(class_mask & class_bit)

    normalized_text = _normalize_class_text(text)
    aliases = CLASS_ALIASES.get(class_code, {class_code})
    tokens = _class_tokens(text)
    normalized_tokens = {_normalize_class_text(token) for token in tokens}
    return any(_normalize_class_text(alias) in normalized_tokens or _normalize_class_text(alias) in normalized_text for alias in aliases)


def _character_class_code(character_class: str | None) -> str | None:
    if character_class is None:
        return None
    normalized = str(character_class).strip().lower()
    if not normalized:
        return None
    normalized_key = _normalize_class_text(normalized)
    if normalized_key in UNKNOWN_CLASS_TOKENS:
        return None
    return CLASS_CODE_BY_NAME.get(normalized, CLASS_CODE_BY_NAME.get(normalized.replace(" ", ""), normalized.upper()))


def _class_tokens(value: str) -> set[str]:
    return {token.upper() for token in re.findall(r"[A-Za-z]+", value)}


def _normalize_class_text(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", value.upper())


def _coerce_non_negative_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value.is_integer() and value >= 0 else None

    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = int(text, 10)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _effective_ratio(combat: dict[str, Any]) -> float | None:
    ratio = _as_float(combat.get("ratio"))
    if ratio is not None:
        return ratio
    damage = _as_float(combat.get("damage"))
    delay = _as_float(combat.get("delay"))
    if damage is not None and delay is not None and delay > 0:
        return damage / delay
    return None


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


def _is_no_drop(flags: Any) -> bool:
    return "NO_DROP" in _flag_tokens(flags)


def _flag_tokens(flags: Any) -> set[str]:
    if flags is None:
        return set()
    return {token.strip().upper() for token in str(flags).replace(";", ",").replace(" ", ",").split(",") if token.strip()}


def _stat_output_name(column_name: str) -> str:
    return {
        "astr": "str",
        "asta": "sta",
        "aagi": "agi",
        "adex": "dex",
        "awis": "wis",
        "aint": "int",
        "acha": "cha",
    }.get(column_name, column_name)


def _normalize_slot(value: Any) -> str:
    return str(value or "").strip().upper().replace(" ", "_").replace("-", "_")


def _slot_key(slot: str, slot_index: int) -> str:
    if slot in DUPLICATE_EQUIPMENT_SLOTS or slot_index != 1:
        return f"{slot}_{slot_index}"
    return slot


def _slot_label(slot: str, slot_index: int) -> str:
    text = slot.replace("_", " ").title()
    if slot in DUPLICATE_EQUIPMENT_SLOTS or slot_index != 1:
        return f"{text} {slot_index}"
    return text


def _fetch_character_or_404(connection: sqlite3.Connection, character_name: str) -> sqlite3.Row:
    normalized_name = character_name.strip().lower()
    if not normalized_name:
        raise HTTPException(status_code=400, detail="character_name must not be blank")

    row = connection.execute(
        """
        SELECT character_name, character_class, server
        FROM characters
        WHERE lower(character_name) = ?
        LIMIT 1
        """,
        (normalized_name,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Character not found")
    return row


def _normalize_optional_server(server: Any) -> str | None:
    if server is None:
        return None
    normalized = str(server).strip().lower()
    return normalized or None


def _connect_or_503(db_path: str | Path) -> sqlite3.Connection:
    try:
        return connect_readonly(db_path)
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"SQLite database is not readable: {exc}") from exc


def _row_has_key(row: sqlite3.Row, key: str) -> bool:
    return key in row.keys()


def _none_as_zero(value: Any) -> int:
    parsed = _as_int(value)
    return parsed if parsed is not None else 0


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

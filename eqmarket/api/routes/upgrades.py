from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request

from eqmarket.api.db import connect_readonly
from eqmarket.api.item_sources import fetch_item_sources_by_id
from eqmarket.slot_masks import KNOWN_LUCY_SLOT_LABEL_SET, decode_lucy_slot_mask


UpgradeSourceFilter = Literal["owned", "market", "all"]

DEFAULT_LIMIT = 50
DEFAULT_LOCAL_LISTING_MAX_AGE_DAYS = 30
MARKET_CANDIDATE_SCAN_LIMIT = 2000
NON_EQUIPMENT_INVENTORY_AREAS = ("carried", "bank", "shared_bank")
AREA_ORDER = {"carried": 0, "bank": 1, "shared_bank": 2}
DUPLICATE_EQUIPMENT_SLOTS = {"EAR", "WRIST", "FINGER"}
DEFAULT_UPGRADE_STATS = ("ac", "hp")

CANONICAL_ITEM_TYPE_FILTERS = (
    "Armor",
    "Augmentation",
    "Aug_1Hand",
    "Aug_2Hand",
    "Aug_Range",
    "Aug_Shield",
    "Shield",
    "Weapon",
    "Weapon_1Hand",
    "Weapon_2Hand",
    "Weapon_H2H",
    "Weapon_Range",
    "Weapon_Throw",
    "Weapon_Arrow",
    "Bag",
    "Food",
    "Drink",
    "Trophy",
    "Familiar",
)
ITEM_TYPE_FILTER_BY_KEY = {re.sub(r"[^A-Z0-9]+", "", label.upper()): label for label in CANONICAL_ITEM_TYPE_FILTERS}
ITEM_TYPE_FILTER_ALIASES = {
    "AUG": "Augmentation",
    "AUGMENT": "Augmentation",
    "AUGMENTATION1HAND": "Aug_1Hand",
    "AUGMENTATION2HAND": "Aug_2Hand",
    "AUGMENTATIONRANGE": "Aug_Range",
    "AUGMENTATIONSHIELD": "Aug_Shield",
    "ONEHAND": "Weapon_1Hand",
    "1HAND": "Weapon_1Hand",
    "TWOHAND": "Weapon_2Hand",
    "2HAND": "Weapon_2Hand",
    "H2H": "Weapon_H2H",
    "HANDTOHAND": "Weapon_H2H",
    "RANGED": "Weapon_Range",
    "RANGE": "Weapon_Range",
    "THROWN": "Weapon_Throw",
    "THROWING": "Weapon_Throw",
    "ARROW": "Weapon_Arrow",
}
ARMOR_TYPE_CODES = {"10", "29", "72"}
SHIELD_TYPE_CODES = {"8"}
AUGMENTATION_TYPE_CODES = {"54"}
WEAPON_1H_TYPE_CODES = {"0", "2", "3"}
WEAPON_2H_TYPE_CODES = {"1", "4", "35"}
WEAPON_H2H_TYPE_CODES = {"38", "45"}
WEAPON_RANGE_TYPE_CODES = {"5"}
WEAPON_THROW_TYPE_CODES = {"7"}
WEAPON_ARROW_TYPE_CODES = {"27"}
BAG_TYPE_CODES = {"67"}
FOOD_TYPE_CODES = {"14"}
DRINK_TYPE_CODES = {"15"}
TROPHY_TYPE_CODES = {"68"}
FAMILIAR_TYPE_CODES = {"69"}
WEAPON_TYPE_CODES = (
    WEAPON_1H_TYPE_CODES
    | WEAPON_2H_TYPE_CODES
    | WEAPON_H2H_TYPE_CODES
    | WEAPON_RANGE_TYPE_CODES
    | WEAPON_THROW_TYPE_CODES
    | WEAPON_ARROW_TYPE_CODES
)

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

UPGRADE_STAT_FIELDS = (
    "ac",
    "hp",
    "mana",
    "endurance",
    "hp_regen",
    "mana_regen",
    "endurance_regen",
    "str",
    "sta",
    "agi",
    "dex",
    "wis",
    "int",
    "cha",
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
    "resists_total",
    "base_stats_total",
    "damage",
    "delay",
    "ratio",
    "haste",
)

UPGRADE_STAT_ALIASES = {
    "MR": "sv_magic",
    "MAGIC": "sv_magic",
    "MAGICRESIST": "sv_magic",
    "SV_MAGIC": "sv_magic",
    "FR": "sv_fire",
    "FIRE": "sv_fire",
    "FIRERESIST": "sv_fire",
    "SV_FIRE": "sv_fire",
    "CR": "sv_cold",
    "COLD": "sv_cold",
    "COLDRESIST": "sv_cold",
    "SV_COLD": "sv_cold",
    "PR": "sv_poison",
    "POISON": "sv_poison",
    "POISONRESIST": "sv_poison",
    "SV_POISON": "sv_poison",
    "DR": "sv_disease",
    "DISEASE": "sv_disease",
    "DISEASERESIST": "sv_disease",
    "SV_DISEASE": "sv_disease",
    "RESISTS": "resists_total",
    "RESISTSTOTAL": "resists_total",
    "BASESTATS": "base_stats_total",
    "BASESTATSTOTAL": "base_stats_total",
    "ATTACKRATIO": "ratio",
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
    item_type: str | None = Query(None, min_length=1),
    class_filter: str | None = Query(None, min_length=1),
    stats: str = Query(",".join(DEFAULT_UPGRADE_STATS), min_length=1),
    better_only: bool = Query(True),
    limit: int = Query(DEFAULT_LIMIT, gt=0, le=200),
    local_listing_max_age_days: int = Query(DEFAULT_LOCAL_LISTING_MAX_AGE_DAYS, ge=1, le=3650),
) -> dict[str, Any]:
    selected_stats = _parse_upgrade_stats(stats)
    item_type_filter = _normalize_optional_item_type_filter(item_type)
    selected_class_filter = _normalize_optional_class_filter(class_filter)
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
    filter_character_class = selected_class_filter or character_class
    exact_class_code = _character_class_code(filter_character_class)
    inferred_class_codes = None if exact_class_code is not None else _infer_possible_character_classes(equipment)
    candidates = _upgrade_candidates(
        raw_candidates,
        equipment=equipment,
        slot_targets=slot_targets,
        character_class=filter_character_class,
        possible_class_codes=inferred_class_codes,
        selected_stats=selected_stats,
        better_only=better_only,
        max_price_pp=max_price_pp,
        item_type_filter=item_type_filter,
    )
    candidates.sort(key=lambda candidate: _candidate_sort_key(candidate, selected_stats))
    candidates = candidates[:limit]

    return {
        "character_name": character["character_name"],
        "server": character["server"],
        "character_class": character_class,
        "stats": selected_stats,
        "better_only": better_only,
        "source": source,
        "slot": _normalize_optional_slot_filter(slot),
        "item_type": item_type_filter,
        "class_filter": selected_class_filter,
        "effective_classes": _effective_class_codes_payload(exact_class_code, inferred_class_codes),
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

    _attach_item_sources(connection, candidates)
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


def _attach_item_sources(connection: sqlite3.Connection, candidates: list[dict[str, Any]]) -> None:
    item_ids = sorted({int(candidate["item"]["item_id"]) for candidate in candidates})
    sources_by_item_id = fetch_item_sources_by_id(connection, item_ids)
    for candidate in candidates:
        item_id = int(candidate["item"]["item_id"])
        candidate["item"]["sources"] = sources_by_item_id.get(item_id, [])


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
    possible_class_codes: set[str] | None,
    selected_stats: list[str],
    better_only: bool,
    max_price_pp: int | None,
    item_type_filter: str | None,
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
        if not _item_type_matches(raw_candidate["item"], item_type_filter):
            continue
        if not _class_compatible(raw_candidate["item"]["classes"], character_class, possible_class_codes):
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
            if not _matches_selected_stats(deltas, selected_stats, better_only):
                continue
            score = _selection_score(deltas, selected_stats)

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
        "sources": [],
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


def _matches_selected_stats(deltas: dict[str, Any], selected_stats: list[str], better_only: bool) -> bool:
    if not better_only:
        return True

    values = [_delta_number(deltas, stat) for stat in selected_stats]
    if any(value is None for value in values):
        return False
    return all(value >= 0 for value in values if value is not None) and any(value > 0 for value in values if value is not None)


def _selection_score(deltas: dict[str, Any], selected_stats: list[str]) -> float:
    score = 0.0
    stat_count = len(selected_stats)
    for index, stat in enumerate(selected_stats):
        value = _delta_number(deltas, stat)
        if value is not None:
            score += value * (stat_count - index)
    return round(score, 4)


def _candidate_sort_key(candidate: dict[str, Any], selected_stats: list[str]) -> tuple[Any, ...]:
    source_rank = {"owned": 0, "local_listing": 1, "market_price": 2}.get(candidate["source"], 9)
    cost = candidate["cost_pp"]
    stat_order: list[Any] = []
    for stat in selected_stats:
        value = _delta_number(candidate["deltas"], stat)
        stat_order.extend((1, 0.0) if value is None else (0, -value))

    return (
        *stat_order,
        source_rank,
        cost if cost is not None else 10**12,
        str(candidate["candidate"]["name"]).lower(),
        int(candidate["candidate"]["item_id"]),
        str(candidate["slot_key"]),
    )


def _parse_upgrade_stats(raw_stats: str) -> list[str]:
    selected_stats: list[str] = []
    invalid_stats: list[str] = []

    for raw_stat in re.split(r"[,|]+", raw_stats):
        if not raw_stat.strip():
            continue
        stat = _normalize_upgrade_stat(raw_stat)
        if stat is None:
            invalid_stats.append(raw_stat.strip())
            continue
        if stat not in selected_stats:
            selected_stats.append(stat)

    if invalid_stats:
        valid = ", ".join(UPGRADE_STAT_FIELDS)
        invalid = ", ".join(invalid_stats)
        raise HTTPException(status_code=400, detail=f"Unknown upgrade stat(s): {invalid}. Valid stats: {valid}")
    if not selected_stats:
        raise HTTPException(status_code=400, detail="At least one upgrade stat is required")
    return selected_stats


def _normalize_upgrade_stat(value: str) -> str | None:
    normalized = _normalize_class_text(value)
    alias = UPGRADE_STAT_ALIASES.get(normalized)
    if alias is not None:
        return alias

    key = value.strip().lower().replace(" ", "_").replace("-", "_")
    return key if key in UPGRADE_STAT_FIELDS else None


def _normalize_optional_class_filter(class_filter: str | None) -> str | None:
    if class_filter is None:
        return None

    value = class_filter.strip()
    if not value:
        return None
    if _normalize_class_text(value) in {"ALL", "AUTO", "ANY"}:
        return None

    class_code = _character_class_code(value)
    if class_code is None:
        valid = ", ".join(CLASS_BIT_BY_CODE)
        raise HTTPException(status_code=400, detail=f"Unknown character class: {class_filter}. Valid classes: {valid}")
    return class_code


def _effective_class_codes_payload(
    exact_class_code: str | None,
    inferred_class_codes: set[str] | None,
) -> list[str] | None:
    if exact_class_code is not None:
        return [exact_class_code]
    if inferred_class_codes:
        return sorted(inferred_class_codes, key=lambda code: CLASS_BIT_BY_CODE.get(code, 10**9))
    return None


def _normalize_optional_item_type_filter(item_type: str | None) -> str | None:
    if item_type is None:
        return None

    value = item_type.strip()
    if not value:
        return None

    key = _normalize_item_type_key(value)
    if key == "ALL":
        return None
    if key in ITEM_TYPE_FILTER_BY_KEY:
        return ITEM_TYPE_FILTER_BY_KEY[key]
    if key in ITEM_TYPE_FILTER_ALIASES:
        return ITEM_TYPE_FILTER_ALIASES[key]
    return value


def _item_type_matches(item: dict[str, Any], item_type_filter: str | None) -> bool:
    if item_type_filter is None:
        return True

    filter_key = _normalize_item_type_key(item_type_filter)
    raw_key = _normalize_item_type_key(item.get("item_type"))
    type_code = _item_type_code(item.get("item_type"))

    if raw_key == filter_key or (type_code is not None and type_code == item_type_filter.strip()):
        return True

    if item_type_filter == "Armor":
        return _is_armor_type(item, type_code, raw_key)
    if item_type_filter == "Augmentation":
        return _matches_type_group(type_code, raw_key, AUGMENTATION_TYPE_CODES, {"AUGMENTATION", "AUGMENT"})
    if item_type_filter in {"Aug_1Hand", "Aug_2Hand", "Aug_Range", "Aug_Shield"}:
        return _matches_type_group(type_code, raw_key, AUGMENTATION_TYPE_CODES, {"AUGMENTATION", "AUGMENT", filter_key})
    if item_type_filter == "Shield":
        return _matches_type_group(type_code, raw_key, SHIELD_TYPE_CODES, {"SHIELD"})
    if item_type_filter == "Weapon":
        return _is_weapon_type(item, type_code, raw_key)
    if item_type_filter == "Weapon_1Hand":
        return _matches_type_group(type_code, raw_key, WEAPON_1H_TYPE_CODES, {"1HSLASHING", "1HBLUNT", "PIERCING", "1HPIERCING", "WEAPON1HAND"})
    if item_type_filter == "Weapon_2Hand":
        return _matches_type_group(type_code, raw_key, WEAPON_2H_TYPE_CODES, {"2HSLASHING", "2HBLUNT", "2HPIERCING", "WEAPON2HAND"})
    if item_type_filter == "Weapon_H2H":
        return _matches_type_group(type_code, raw_key, WEAPON_H2H_TYPE_CODES, {"HANDTOHAND", "H2H", "WEAPONH2H"})
    if item_type_filter == "Weapon_Range":
        return _matches_type_group(type_code, raw_key, WEAPON_RANGE_TYPE_CODES, {"ARCHERY", "BOW", "RANGE", "RANGED", "WEAPONRANGE"})
    if item_type_filter == "Weapon_Throw":
        return _matches_type_group(type_code, raw_key, WEAPON_THROW_TYPE_CODES, {"THROW", "THROWN", "THROWING", "WEAPONTHROW"})
    if item_type_filter == "Weapon_Arrow":
        return _matches_type_group(type_code, raw_key, WEAPON_ARROW_TYPE_CODES, {"ARROW", "FLETCHEDARROWS", "WEAPONARROW"})
    if item_type_filter == "Bag":
        return _matches_type_group(type_code, raw_key, BAG_TYPE_CODES, {"BAG", "CONTAINER"})
    if item_type_filter == "Food":
        return _matches_type_group(type_code, raw_key, FOOD_TYPE_CODES, {"FOOD"})
    if item_type_filter == "Drink":
        return _matches_type_group(type_code, raw_key, DRINK_TYPE_CODES, {"DRINK"})
    if item_type_filter == "Trophy":
        return _matches_type_group(type_code, raw_key, TROPHY_TYPE_CODES, {"TROPHY"})
    if item_type_filter == "Familiar":
        return _matches_type_group(type_code, raw_key, FAMILIAR_TYPE_CODES, {"FAMILIAR"})

    return False


def _is_armor_type(item: dict[str, Any], type_code: str | None, raw_key: str) -> bool:
    if _matches_type_group(type_code, raw_key, ARMOR_TYPE_CODES, {"ARMOR", "JEWELRY"}):
        return True
    if _is_weapon_type(item, type_code, raw_key):
        return False
    if _matches_type_group(type_code, raw_key, SHIELD_TYPE_CODES | AUGMENTATION_TYPE_CODES | BAG_TYPE_CODES | FOOD_TYPE_CODES | DRINK_TYPE_CODES, {"SHIELD", "AUGMENTATION", "AUGMENT", "BAG", "CONTAINER", "FOOD", "DRINK"}):
        return False
    return bool(item.get("slot_labels"))


def _is_weapon_type(item: dict[str, Any], type_code: str | None, raw_key: str) -> bool:
    if _matches_type_group(type_code, raw_key, WEAPON_TYPE_CODES, {"WEAPON", "1HSLASHING", "2HSLASHING", "PIERCING", "1HPIERCING", "1HBLUNT", "2HBLUNT", "2HPIERCING", "HANDTOHAND", "H2H", "ARCHERY", "BOW", "THROW", "THROWN", "THROWING", "ARROW"}):
        return True
    combat = item.get("combat", {})
    return (_as_int(combat.get("damage")) or 0) > 0 and (_as_int(combat.get("delay")) or 0) > 0


def _matches_type_group(type_code: str | None, raw_key: str, codes: set[str], names: set[str]) -> bool:
    return (type_code is not None and type_code in codes) or raw_key in names


def _item_type_code(value: Any) -> str | None:
    parsed = _coerce_non_negative_int(value)
    return str(parsed) if parsed is not None else None


def _normalize_item_type_key(value: Any) -> str:
    return _normalize_class_text("" if value is None else str(value))


def _delta_number(deltas: dict[str, Any], stat: str) -> float | None:
    value = deltas.get(stat)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _infer_possible_character_classes(equipment: dict[str, dict[str, Any]]) -> set[str] | None:
    possible_classes: set[str] | None = None
    all_class_codes = set(CLASS_BIT_BY_CODE)

    for slot in equipment.values():
        item = slot.get("item")
        if item is None:
            continue

        item_class_codes = _class_codes_from_value(item.get("classes"))
        if not item_class_codes or item_class_codes == all_class_codes:
            continue

        possible_classes = set(item_class_codes) if possible_classes is None else possible_classes & item_class_codes
        if not possible_classes:
            return None

    return possible_classes


def _class_compatible(
    item_classes: Any,
    character_class: str | None,
    possible_class_codes: set[str] | None = None,
) -> bool:
    text = "" if item_classes is None else str(item_classes).strip()
    if not text:
        return True
    if "ALL" in _class_tokens(text):
        return True

    class_code = _character_class_code(character_class)
    if class_code is not None:
        item_class_codes = _class_codes_from_value(text)
        return item_class_codes is None or class_code in item_class_codes

    if possible_class_codes:
        item_class_codes = _class_codes_from_value(text)
        return item_class_codes is None or bool(item_class_codes & possible_class_codes)

    return True


def _class_codes_from_value(item_classes: Any) -> set[str] | None:
    text = "" if item_classes is None else str(item_classes).strip()
    if not text:
        return None
    if "ALL" in _class_tokens(text):
        return set(CLASS_BIT_BY_CODE)

    class_mask = _coerce_non_negative_int(text)
    if class_mask is not None:
        return {class_code for class_code, class_bit in CLASS_BIT_BY_CODE.items() if class_mask & class_bit}

    normalized_text = _normalize_class_text(text)
    normalized_tokens = {_normalize_class_text(token) for token in _class_tokens(text)}
    class_codes: set[str] = set()
    for class_code, aliases in CLASS_ALIASES.items():
        if any(
            _normalize_class_text(alias) in normalized_tokens or _normalize_class_text(alias) in normalized_text
            for alias in aliases
        ):
            class_codes.add(class_code)
    return class_codes or None


def _character_class_code(character_class: str | None) -> str | None:
    if character_class is None:
        return None
    normalized = str(character_class).strip().lower()
    if not normalized:
        return None
    normalized_key = _normalize_class_text(normalized)
    if normalized_key in UNKNOWN_CLASS_TOKENS:
        return None

    class_code = CLASS_CODE_BY_NAME.get(normalized, CLASS_CODE_BY_NAME.get(normalized.replace(" ", "")))
    if class_code is not None:
        return class_code

    upper_value = normalized.upper()
    return upper_value if upper_value in CLASS_BIT_BY_CODE else None


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

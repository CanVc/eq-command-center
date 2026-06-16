from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from eqmarket.db import init_db
from eqmarket.log_parser import normalize_item_name
from eqmarket.sources.lucy import LucyClient, LucyLookupError, as_float, as_int, raw_payload
from eqmarket.sources.lucy import PARSER_VERSION as LUCY_PARSER_VERSION


@dataclass
class EnrichPendingStats:
    pending_seen: int = 0
    local_items_resolved: int = 0
    items_imported: int = 0
    spells_imported: int = 0
    item_effects_imported: int = 0
    listings_linked: int = 0
    not_found: int = 0
    failed: int = 0


@dataclass(frozen=True)
class PendingItem:
    normalized_name: str
    display_name: str


ITEM_INT_FIELDS = {
    "ac": "ac",
    "hp": "hp",
    "mana": "mana",
    "endur": "endurance",
    "regen": "hp_regen",
    "manaregen": "mana_regen",
    "endurregen": "endurance_regen",
    "astr": "astr",
    "asta": "asta",
    "aagi": "aagi",
    "adex": "adex",
    "awis": "awis",
    "aint": "aint",
    "acha": "acha",
    "heroic_str": "heroic_str",
    "heroic_sta": "heroic_sta",
    "heroic_agi": "heroic_agi",
    "heroic_dex": "heroic_dex",
    "heroic_wis": "heroic_wis",
    "heroic_int": "heroic_int",
    "heroic_cha": "heroic_cha",
    "svmagic": "sv_magic",
    "svfire": "sv_fire",
    "svcold": "sv_cold",
    "svpoison": "sv_poison",
    "svdisease": "sv_disease",
    "damage": "damage",
    "delay": "delay",
    "haste": "haste",
    "reqlevel": "required_level",
    "reclevel": "recommended_level",
    "icon": "icon_id",
}

SPELL_INT_FIELDS = {
    "mana": "mana_cost",
    "endurcost": "endurance_cost",
    "casttime": "cast_time_ms",
    "recasttime": "recast_time_ms",
    "recoverytime": "recovery_time_ms",
    "duration": "duration_ticks",
    "durationformula": "duration_formula",
}


def enrich_pending_items(db_path: Path, limit: int = 25, source_server: str = "Live") -> EnrichPendingStats:
    init_db(db_path)
    stats = EnrichPendingStats()
    client = LucyClient(source=source_server)

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        pending_items = _load_pending_items(connection, limit)

        for pending in pending_items:
            stats.pending_seen += 1
            try:
                existing_item_id = _find_existing_item_id(connection, pending.normalized_name)
                if existing_item_id is not None:
                    linked = _link_existing_listings(connection, pending.normalized_name, existing_item_id)
                    stats.listings_linked += linked
                    _mark_pending_resolved(connection, pending, existing_item_id)
                    stats.local_items_resolved += 1
                    continue

                item_id = client.lookup_item_id_by_exact_name(pending.display_name)
                if item_id is None:
                    _mark_pending_not_found(connection, pending, "Lucy exact lookup returned no result")
                    stats.not_found += 1
                    continue

                item = client.fetch_item_raw(item_id)
                imported_item_id = upsert_lucy_item(connection, item.fields)
                stats.items_imported += 1

                spells, effects = import_item_effect_spells(connection, client, item.fields, imported_item_id)
                stats.spells_imported += spells
                stats.item_effects_imported += effects

                linked = _link_existing_listings(connection, pending.normalized_name, imported_item_id)
                stats.listings_linked += linked
                _mark_pending_resolved(connection, pending, imported_item_id)
            except LucyLookupError as exc:
                _mark_pending_failed(connection, pending, str(exc))
                stats.failed += 1
            except OSError as exc:
                # Network / TLS / timeout: keep it retryable.
                _mark_pending_failed(connection, pending, f"Network error: {exc}")
                stats.failed += 1

    return stats


def upsert_lucy_item(connection: sqlite3.Connection, fields: dict[str, str]) -> int:
    item_id = as_int(fields, "id")
    name = fields.get("name")
    if item_id is None or not name:
        raise LucyLookupError("Lucy item raw missing id or name")

    normalized_name = normalize_item_name(name)
    damage = as_int(fields, "damage")
    delay = as_int(fields, "delay")
    ratio = round(damage / delay, 4) if damage is not None and delay and delay > 0 else None

    values: dict[str, object] = {
        "item_id": item_id,
        "name": name,
        "normalized_name": normalized_name,
        "item_type": fields.get("itemtype"),
        "slot": fields.get("slots"),
        "classes": fields.get("classes"),
        "races": fields.get("races"),
        "ratio": ratio,
        "flags": _item_flags(fields),
        "source_primary": "lucy",
        "raw_payload": raw_payload(fields),
        "parser_version": LUCY_PARSER_VERSION,
    }
    for source_key, column in ITEM_INT_FIELDS.items():
        values[column] = as_int(fields, source_key)

    columns = list(values)
    placeholders = ", ".join("?" for _ in columns)
    update_clause = ", ".join(
        f"{column} = excluded.{column}" for column in columns if column != "item_id"
    )
    connection.execute(
        f"""
        INSERT INTO items ({", ".join(columns)}, last_imported_at, updated_at)
        VALUES ({placeholders}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(item_id) DO UPDATE SET
            {update_clause},
            last_imported_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        """,
        tuple(values[column] for column in columns),
    )
    return item_id


def import_item_effect_spells(
    connection: sqlite3.Connection,
    client: LucyClient,
    item_fields: dict[str, str],
    item_id: int,
) -> tuple[int, int]:
    spells_imported = 0
    effects_imported = 0
    connection.execute("DELETE FROM item_effects WHERE item_id = ?", (item_id,))

    for effect_slot in range(0, 12):
        spell_id = as_int(item_fields, f"spellid{effect_slot}")
        if spell_id is None or spell_id <= 0:
            continue

        spell = client.fetch_spell_raw(spell_id)
        upsert_lucy_spell(connection, spell.fields)
        spells_imported += 1

        connection.execute(
            """
            INSERT OR REPLACE INTO item_effects (
                item_id, effect_slot, spell_id, trigger_type, effect_type_raw,
                cast_time_ms, required_level, effective_level, proc_rate, charges, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                effect_slot,
                spell_id,
                _trigger_type(as_int(item_fields, f"effecttype{effect_slot}")),
                as_int(item_fields, f"effecttype{effect_slot}"),
                as_int(item_fields, f"casttime{effect_slot}"),
                as_int(item_fields, f"level{effect_slot}"),
                as_int(item_fields, f"efflevel{effect_slot}"),
                as_int(item_fields, f"procrate{effect_slot}"),
                as_int(item_fields, f"charges{effect_slot}"),
                None,
            ),
        )
        effects_imported += 1

    return spells_imported, effects_imported


def upsert_lucy_spell(connection: sqlite3.Connection, fields: dict[str, str]) -> int:
    spell_id = as_int(fields, "id")
    name = fields.get("name")
    if spell_id is None or not name:
        raise LucyLookupError("Lucy spell raw missing id or name")

    normalized_name = normalize_item_name(name)
    values: dict[str, object] = {
        "spell_id": spell_id,
        "name": name,
        "normalized_name": normalized_name,
        "spell_type": fields.get("spelltype"),
        "target_type": fields.get("targettype"),
        "skill": fields.get("skill"),
        "resist_type": fields.get("resisttype"),
        "range_value": as_float(fields, "range"),
        "aoe_range_value": as_float(fields, "aoerange"),
        "source_server": "Live",
        "source_primary": "lucy",
        "raw_payload": raw_payload(fields),
        "parser_version": LUCY_PARSER_VERSION,
    }
    for source_key, column in SPELL_INT_FIELDS.items():
        values[column] = as_int(fields, source_key)

    columns = list(values)
    placeholders = ", ".join("?" for _ in columns)
    update_clause = ", ".join(
        f"{column} = excluded.{column}" for column in columns if column != "spell_id"
    )
    connection.execute(
        f"""
        INSERT INTO spells ({", ".join(columns)}, last_imported_at, updated_at)
        VALUES ({placeholders}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(spell_id) DO UPDATE SET
            {update_clause},
            last_imported_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        """,
        tuple(values[column] for column in columns),
    )

    connection.execute("DELETE FROM spell_effect_slots WHERE spell_id = ?", (spell_id,))
    for slot_index in range(1, 13):
        attrib = as_int(fields, f"attrib{slot_index}")
        base = as_int(fields, f"base{slot_index}")
        max_value = as_int(fields, f"max{slot_index}")
        calc = as_int(fields, f"calc{slot_index}")
        if attrib is None and base is None and max_value is None and calc is None:
            continue
        connection.execute(
            """
            INSERT INTO spell_effect_slots (
                spell_id, slot_index, effect_attribute_id, base_value, max_value, calc_id, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (spell_id, slot_index, attrib, base, max_value, calc, None),
        )

    return spell_id


def _load_pending_items(connection: sqlite3.Connection, limit: int) -> list[PendingItem]:
    rows = connection.execute(
        """
        SELECT normalized_name, display_name
        FROM pending_items
        WHERE status = 'pending'
        ORDER BY first_seen_at, normalized_name
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [PendingItem(normalized_name=row[0], display_name=row[1]) for row in rows]


def _find_existing_item_id(connection: sqlite3.Connection, normalized_name: str) -> int | None:
    row = connection.execute(
        "SELECT item_id FROM items WHERE normalized_name = ?",
        (normalized_name,),
    ).fetchone()
    return int(row[0]) if row else None


def _link_existing_listings(connection: sqlite3.Connection, normalized_name: str, item_id: int) -> int:
    cursor = connection.execute(
        """
        UPDATE market_listings
        SET item_id = ?
        WHERE normalized_item_name = ? AND item_id IS NULL
        """,
        (item_id, normalized_name),
    )
    return cursor.rowcount


def _mark_pending_resolved(connection: sqlite3.Connection, pending: PendingItem, item_id: int) -> None:
    connection.execute(
        """
        UPDATE pending_items
        SET status = 'resolved', notes = ?, last_seen_at = CURRENT_TIMESTAMP
        WHERE normalized_name = ?
        """,
        (f"Resolved to Lucy item_id={item_id}", pending.normalized_name),
    )


def _mark_pending_not_found(connection: sqlite3.Connection, pending: PendingItem, notes: str) -> None:
    connection.execute(
        """
        UPDATE pending_items
        SET status = 'not_found', notes = ?, last_seen_at = CURRENT_TIMESTAMP
        WHERE normalized_name = ?
        """,
        (notes, pending.normalized_name),
    )


def _mark_pending_failed(connection: sqlite3.Connection, pending: PendingItem, notes: str) -> None:
    connection.execute(
        """
        UPDATE pending_items
        SET notes = ?, last_seen_at = CURRENT_TIMESTAMP
        WHERE normalized_name = ?
        """,
        (notes[:1000], pending.normalized_name),
    )


def _item_flags(fields: dict[str, str]) -> str | None:
    flags: list[str] = []
    for key, label in [
        ("magic", "MAGIC"),
        ("nodrop", "NO_DROP"),
        ("norent", "NO_RENT"),
        ("attuneable", "ATTUNEABLE"),
        ("artifact", "ARTIFACT"),
    ]:
        if as_int(fields, key):
            flags.append(label)
    return ",".join(flags) if flags else None


def _trigger_type(effect_type_raw: int | None) -> str:
    # Lucy effecttype mappings vary by era/source; keep a safe raw value and a
    # conservative text bucket for now.
    return "unknown" if effect_type_raw is not None else "unknown"

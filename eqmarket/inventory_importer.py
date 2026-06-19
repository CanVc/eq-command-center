from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eqmarket.db import init_db
from eqmarket.log_parser import normalize_item_name


PARSER_VERSION = "eq_inventory_tsv_v1"
STARTER_IMPORT_FLAGS = "STARTER,NO_TRADE_IMPORT"
UNKNOWN_CHARACTER_CLASS = "UNKNOWN"

_REQUIRED_HEADERS = {"location", "name", "id", "count", "slots"}
_INVENTORY_FILENAME_SUFFIX_RE = re.compile(r"-Inventory(?:\.txt)?$", re.IGNORECASE)
_TRAILING_AUGMENT_RE = re.compile(
    r"(?i)(?:-(?:aug|augment|augslot|augment\s*slot)\s*#?(?P<dash_index>\d+)|\s+Aug(?P<space_index>\d+))$"
)
_TRAILING_SLOT_RE = re.compile(r"(?i)-Slot(?P<slot_index>\d+)$")
_GENERAL_LOCATION_RE = re.compile(r"(?i)^General\s*(?P<index>\d+)$")
_BANK_LOCATION_RE = re.compile(r"(?i)^Bank\s*(?P<index>\d+)$")
_SHARED_BANK_LOCATION_RE = re.compile(r"(?i)^Shared\s*Bank\s*(?P<index>\d+)$")
_CONTAINER_NAME_RE = re.compile(
    r"\b(?:bag|backpack|box|chest|crate|haversack|pouch|quiver|sack|satchel|toolbox)\b",
    re.IGNORECASE,
)

_EQUIPMENT_LOCATION_ALIASES: dict[str, tuple[str, int | None]] = {
    "charm": ("CHARM", 1),
    "ear": ("EAR", None),
    "ears": ("EAR", None),
    "left ear": ("EAR", 1),
    "right ear": ("EAR", 2),
    "head": ("HEAD", 1),
    "face": ("FACE", 1),
    "neck": ("NECK", 1),
    "shoulder": ("SHOULDERS", 1),
    "shoulders": ("SHOULDERS", 1),
    "arms": ("ARMS", 1),
    "back": ("BACK", 1),
    "wrist": ("WRIST", None),
    "wrists": ("WRIST", None),
    "left wrist": ("WRIST", 1),
    "right wrist": ("WRIST", 2),
    "range": ("RANGE", 1),
    "ranged": ("RANGE", 1),
    "hands": ("HANDS", 1),
    "primary": ("PRIMARY", 1),
    "secondary": ("SECONDARY", 1),
    "finger": ("FINGER", None),
    "fingers": ("FINGER", None),
    "ring": ("FINGER", None),
    "rings": ("FINGER", None),
    "left finger": ("FINGER", 1),
    "right finger": ("FINGER", 2),
    "left ring": ("FINGER", 1),
    "right ring": ("FINGER", 2),
    "chest": ("CHEST", 1),
    "legs": ("LEGS", 1),
    "feet": ("FEET", 1),
    "waist": ("WAIST", 1),
    "power source": ("POWER_SOURCE", 1),
    "powersource": ("POWER_SOURCE", 1),
    "ammo": ("AMMO", 1),
}

_ITEM_STAT_COLUMNS = (
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
)


@dataclass(frozen=True)
class InventoryLocationClassification:
    area: str
    parent_location: str | None
    location_index: int | None
    location_slot_index: int | None
    is_equipment: bool
    equipment_slot: str | None
    explicit_equipment_slot_index: int | None
    is_augment: bool
    augment_parent_location: str | None


@dataclass(frozen=True)
class InventoryDumpItem:
    raw_location: str
    raw_item_name: str
    item_name: str
    normalized_item_name: str
    item_id: int
    quantity: int
    slots: str | None
    area: str
    parent_location: str | None
    location_index: int | None
    location_slot_index: int | None
    is_equipment: bool
    equipment_slot: str | None
    explicit_equipment_slot_index: int | None
    is_container: bool
    is_starter_item: bool
    is_augment: bool
    augment_parent_location: str | None


@dataclass(frozen=True)
class InventoryDumpParseResult:
    items: tuple[InventoryDumpItem, ...]
    rows_seen: int
    empty_rows_skipped: int
    starter_items_seen: int


@dataclass
class InventoryImportStats:
    character_name: str
    server: str
    source_file: str
    source_hash: str
    inventory_import_id: int | None = None
    rows_seen: int = 0
    rows_imported: int = 0
    empty_rows_skipped: int = 0
    starter_items_seen: int = 0
    equipment_items_imported: int = 0
    inventory_items_imported: int = 0
    item_stubs_upserted: int = 0
    pending_items_upserted: int = 0


def infer_character_server_from_inventory_path(path: Path) -> tuple[str, str] | None:
    """Infer ``(<Character>, <server>)`` from ``<Character>_<server>-Inventory.txt``."""

    filename = path.name.strip()
    base_name = _INVENTORY_FILENAME_SUFFIX_RE.sub("", filename)
    if base_name == filename:
        return None

    character_name, separator, server = base_name.rpartition("_")
    if not separator:
        return None

    character_name = character_name.strip()
    server = _normalize_server(server)
    if not character_name or not server:
        return None
    return character_name, server


def parse_inventory_dump(path: Path) -> InventoryDumpParseResult:
    """Parse an EverQuest ``/outputfile inventory`` TSV dump.

    Empty rows are counted for diagnostics but are not returned as current
    inventory records. Starter/no-trade rows keep their raw ``*`` name while the
    normalized name and clean display name drop the suffix.
    """

    items: list[InventoryDumpItem] = []
    rows_seen = 0
    empty_rows_skipped = 0
    starter_items_seen = 0

    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        field_map = _field_map(reader.fieldnames)
        missing_headers = _REQUIRED_HEADERS - set(field_map)
        if missing_headers:
            missing = ", ".join(sorted(missing_headers))
            raise ValueError(f"Inventory dump is missing required TSV column(s): {missing}")

        for row in reader:
            if _row_is_blank(row):
                continue

            rows_seen += 1
            raw_location = _row_value(row, field_map, "location")
            raw_item_name = _row_value(row, field_map, "name")
            id_text = _row_value(row, field_map, "id")
            count_text = _row_value(row, field_map, "count")
            slots = _optional_row_value(row, field_map, "slots")

            if _is_empty_inventory_row(raw_item_name, id_text):
                empty_rows_skipped += 1
                continue

            item_id = _parse_positive_int(id_text, "ID", reader.line_num)
            quantity = _parse_quantity(count_text, reader.line_num)
            is_starter = _is_starter_item_name(raw_item_name)
            if is_starter:
                starter_items_seen += 1
            item_name = _clean_imported_item_name(raw_item_name)
            normalized_name = normalize_item_name(item_name)
            if not item_name or not normalized_name:
                raise ValueError(f"Inventory dump row {reader.line_num} has a blank item name")

            location = classify_inventory_location(raw_location)
            items.append(
                InventoryDumpItem(
                    raw_location=raw_location,
                    raw_item_name=raw_item_name,
                    item_name=item_name,
                    normalized_item_name=normalized_name,
                    item_id=item_id,
                    quantity=quantity,
                    slots=slots,
                    area=location.area,
                    parent_location=location.parent_location,
                    location_index=location.location_index,
                    location_slot_index=location.location_slot_index,
                    is_equipment=location.is_equipment,
                    equipment_slot=location.equipment_slot,
                    explicit_equipment_slot_index=location.explicit_equipment_slot_index,
                    is_container=_looks_like_container_item(item_name),
                    is_starter_item=is_starter,
                    is_augment=location.is_augment,
                    augment_parent_location=location.augment_parent_location,
                )
            )

    return InventoryDumpParseResult(
        items=tuple(items),
        rows_seen=rows_seen,
        empty_rows_skipped=empty_rows_skipped,
        starter_items_seen=starter_items_seen,
    )


def classify_inventory_location(raw_location: str) -> InventoryLocationClassification:
    location = raw_location.strip()
    if not location:
        return InventoryLocationClassification(
            area="carried",
            parent_location=None,
            location_index=None,
            location_slot_index=None,
            is_equipment=False,
            equipment_slot=None,
            explicit_equipment_slot_index=None,
            is_augment=False,
            augment_parent_location=None,
        )

    augment_match = _TRAILING_AUGMENT_RE.search(location)
    if augment_match:
        parent_location = location[: augment_match.start()].strip()
        augment_index = _coerce_int(augment_match.group("dash_index") or augment_match.group("space_index"))
        parent_classification = classify_inventory_location(parent_location)
        return InventoryLocationClassification(
            area=parent_classification.area,
            parent_location=parent_location or None,
            location_index=parent_classification.location_index,
            location_slot_index=augment_index,
            is_equipment=False,
            equipment_slot=None,
            explicit_equipment_slot_index=None,
            is_augment=True,
            augment_parent_location=parent_location or None,
        )

    slot_match = _TRAILING_SLOT_RE.search(location)
    if slot_match:
        parent_location = location[: slot_match.start()].strip()
        slot_index = _coerce_int(slot_match.group("slot_index"))
        parent_equipment = _equipment_location(parent_location)
        if parent_equipment is not None:
            return InventoryLocationClassification(
                area="equipped",
                parent_location=parent_location or None,
                location_index=None,
                location_slot_index=slot_index,
                is_equipment=False,
                equipment_slot=None,
                explicit_equipment_slot_index=None,
                is_augment=True,
                augment_parent_location=parent_location or None,
            )

        return InventoryLocationClassification(
            area=_area_for_base_location(parent_location),
            parent_location=parent_location or None,
            location_index=_location_index(parent_location),
            location_slot_index=slot_index,
            is_equipment=False,
            equipment_slot=None,
            explicit_equipment_slot_index=None,
            is_augment=False,
            augment_parent_location=None,
        )

    equipment = _equipment_location(location)
    if equipment is not None:
        slot, explicit_index = equipment
        return InventoryLocationClassification(
            area="equipped",
            parent_location=None,
            location_index=None,
            location_slot_index=None,
            is_equipment=True,
            equipment_slot=slot,
            explicit_equipment_slot_index=explicit_index,
            is_augment=False,
            augment_parent_location=None,
        )

    return InventoryLocationClassification(
        area=_area_for_base_location(location),
        parent_location=None,
        location_index=_location_index(location),
        location_slot_index=None,
        is_equipment=False,
        equipment_slot=None,
        explicit_equipment_slot_index=None,
        is_augment=False,
        augment_parent_location=None,
    )


def import_inventory_dump(
    db_path: Path,
    file_path: Path,
    *,
    character_name: str | None = None,
    server: str | None = None,
) -> InventoryImportStats:
    inferred = infer_character_server_from_inventory_path(file_path)
    resolved_character = _normalize_character_name(character_name or (inferred[0] if inferred else None))
    resolved_server = _normalize_server(server or (inferred[1] if inferred else None))
    if resolved_character is None:
        raise ValueError("character_name is required when it cannot be inferred from the inventory filename")
    if resolved_server is None:
        raise ValueError("server is required when it cannot be inferred from the inventory filename")

    parse_result = parse_inventory_dump(file_path)
    source_hash = _sha256_file(file_path)
    stats = InventoryImportStats(
        character_name=resolved_character,
        server=resolved_server,
        source_file=str(file_path),
        source_hash=source_hash,
        rows_seen=parse_result.rows_seen,
        rows_imported=len(parse_result.items),
        empty_rows_skipped=parse_result.empty_rows_skipped,
        starter_items_seen=parse_result.starter_items_seen,
    )

    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        _upsert_character(connection, resolved_character, resolved_server)
        import_id = _insert_inventory_import(connection, file_path, parse_result, stats)
        stats.inventory_import_id = import_id

        _replace_current_inventory_state(connection, resolved_character)

        used_equipment_indexes: dict[str, set[int]] = {}
        pending_names_seen: set[str] = set()
        stubbed_item_ids: set[int] = set()
        for item in parse_result.items:
            item_existed = _item_exists(connection, item.item_id)
            _upsert_inventory_item_stub(connection, item)
            if not item_existed and item.item_id not in stubbed_item_ids:
                stats.item_stubs_upserted += 1
                stubbed_item_ids.add(item.item_id)

            if item.is_equipment and item.equipment_slot is not None:
                slot_index = _next_equipment_slot_index(
                    used_equipment_indexes,
                    item.equipment_slot,
                    item.explicit_equipment_slot_index,
                )
                _insert_character_equipment(connection, resolved_character, resolved_server, import_id, item, slot_index)
                stats.equipment_items_imported += 1
            else:
                _insert_character_inventory_item(connection, resolved_character, resolved_server, import_id, item)
                stats.inventory_items_imported += 1

            if not item.is_starter_item and item.normalized_item_name not in pending_names_seen:
                if _enqueue_inventory_item_for_enrichment(connection, item):
                    stats.pending_items_upserted += 1
                pending_names_seen.add(item.normalized_item_name)

        _finalize_inventory_import(connection, import_id, stats)
        _record_inventory_import_run(connection, stats)
        connection.commit()

    return stats


def _field_map(fieldnames: list[str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for fieldname in fieldnames or []:
        normalized = _normalize_header(fieldname)
        if normalized and normalized not in result:
            result[normalized] = fieldname
    return result


def _normalize_header(value: str | None) -> str:
    return "" if value is None else re.sub(r"\s+", "", value.strip().lower())


def _row_value(row: dict[str, str | None], field_map: dict[str, str], name: str) -> str:
    return (row.get(field_map[name]) or "").strip()


def _optional_row_value(row: dict[str, str | None], field_map: dict[str, str], name: str) -> str | None:
    value = _row_value(row, field_map, name)
    return value or None


def _row_is_blank(row: dict[str, str | None]) -> bool:
    for value in row.values():
        if isinstance(value, list):
            if any(str(part).strip() for part in value):
                return False
            continue
        if (value or "").strip():
            return False
    return True


def _is_empty_inventory_row(raw_item_name: str, id_text: str) -> bool:
    lowered_name = raw_item_name.strip().lower()
    if lowered_name == "empty":
        return True
    if not lowered_name and not id_text.strip():
        return True
    return False


def _parse_positive_int(value: str, field_name: str, line_number: int) -> int:
    parsed = _coerce_int(value)
    if parsed is None or parsed <= 0:
        raise ValueError(f"Inventory dump row {line_number} has invalid {field_name}: {value!r}")
    return parsed


def _parse_quantity(value: str, line_number: int) -> int:
    if not value.strip():
        return 1
    parsed = _coerce_int(value)
    if parsed is None:
        raise ValueError(f"Inventory dump row {line_number} has invalid Count: {value!r}")
    return max(parsed, 1)


def _coerce_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def _is_starter_item_name(raw_item_name: str) -> bool:
    return raw_item_name.rstrip().endswith("*")


def _clean_imported_item_name(raw_item_name: str) -> str:
    return re.sub(r"\*+\s*$", "", raw_item_name.strip()).strip()


def _looks_like_container_item(item_name: str) -> bool:
    return bool(_CONTAINER_NAME_RE.search(item_name))


def _normalize_character_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_server(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _location_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("_", " ").replace("-", " ").strip().lower())


def _equipment_location(raw_location: str) -> tuple[str, int | None] | None:
    return _EQUIPMENT_LOCATION_ALIASES.get(_location_key(raw_location))


def _area_for_base_location(raw_location: str) -> str:
    key = _location_key(raw_location)
    if _SHARED_BANK_LOCATION_RE.fullmatch(raw_location.strip()) or key.startswith("shared bank") or key.startswith("sharedbank"):
        return "shared_bank"
    if _BANK_LOCATION_RE.fullmatch(raw_location.strip()) or key.startswith("bank"):
        return "bank"
    return "carried"


def _location_index(raw_location: str) -> int | None:
    stripped = raw_location.strip()
    for pattern in (_GENERAL_LOCATION_RE, _BANK_LOCATION_RE, _SHARED_BANK_LOCATION_RE):
        match = pattern.fullmatch(stripped)
        if match:
            return _coerce_int(match.group("index"))
    return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _upsert_character(connection: sqlite3.Connection, character_name: str, server: str) -> None:
    connection.execute(
        """
        INSERT INTO characters (character_name, character_class, server, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(character_name) DO UPDATE SET
            server = excluded.server,
            updated_at = CURRENT_TIMESTAMP
        """,
        (character_name, UNKNOWN_CHARACTER_CLASS, server),
    )


def _insert_inventory_import(
    connection: sqlite3.Connection,
    file_path: Path,
    parse_result: InventoryDumpParseResult,
    stats: InventoryImportStats,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO inventory_imports (
            character_name, server, source_file, source_hash, source_size_bytes,
            parser_version, rows_seen, rows_imported, starter_items_seen,
            empty_rows_skipped, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed')
        """,
        (
            stats.character_name,
            stats.server,
            str(file_path),
            stats.source_hash,
            file_path.stat().st_size,
            PARSER_VERSION,
            parse_result.rows_seen,
            len(parse_result.items),
            parse_result.starter_items_seen,
            parse_result.empty_rows_skipped,
        ),
    )
    return int(cursor.lastrowid)


def _replace_current_inventory_state(connection: sqlite3.Connection, character_name: str) -> None:
    connection.execute("DELETE FROM character_equipment WHERE character_name = ?", (character_name,))
    connection.execute("DELETE FROM character_inventory_items WHERE character_name = ?", (character_name,))


def _item_exists(connection: sqlite3.Connection, item_id: int) -> bool:
    row = connection.execute("SELECT 1 FROM items WHERE item_id = ?", (item_id,)).fetchone()
    return row is not None


def _upsert_inventory_item_stub(connection: sqlite3.Connection, item: InventoryDumpItem) -> None:
    raw_payload = json.dumps(
        {
            "source": "inventory_dump",
            "raw_item_name": item.raw_item_name,
            "raw_location": item.raw_location,
            "is_starter_item": item.is_starter_item,
            "slots": item.slots,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    connection.execute(
        """
        INSERT INTO items (
            item_id, name, normalized_name, slot, flags, source_primary,
            raw_payload, parser_version, last_imported_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 'inventory_dump', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(item_id) DO UPDATE SET
            name = COALESCE(NULLIF(items.name, ''), excluded.name),
            normalized_name = COALESCE(NULLIF(items.normalized_name, ''), excluded.normalized_name),
            slot = COALESCE(items.slot, excluded.slot),
            flags = CASE
                WHEN excluded.flags IS NULL THEN items.flags
                WHEN items.flags IS NULL OR items.flags = '' THEN excluded.flags
                WHEN instr(items.flags, 'STARTER') = 0 THEN items.flags || ',' || excluded.flags
                ELSE items.flags
            END,
            source_primary = COALESCE(items.source_primary, excluded.source_primary),
            raw_payload = COALESCE(items.raw_payload, excluded.raw_payload),
            parser_version = COALESCE(items.parser_version, excluded.parser_version),
            last_imported_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            item.item_id,
            item.item_name,
            item.normalized_item_name,
            item.slots,
            STARTER_IMPORT_FLAGS if item.is_starter_item else None,
            raw_payload,
            PARSER_VERSION,
        ),
    )


def _next_equipment_slot_index(
    used_indexes: dict[str, set[int]],
    slot: str,
    explicit_index: int | None,
) -> int:
    used_for_slot = used_indexes.setdefault(slot, set())
    if explicit_index is not None and explicit_index > 0 and explicit_index not in used_for_slot:
        used_for_slot.add(explicit_index)
        return explicit_index

    candidate = 1
    while candidate in used_for_slot:
        candidate += 1
    used_for_slot.add(candidate)
    return candidate


def _insert_character_equipment(
    connection: sqlite3.Connection,
    character_name: str,
    server: str,
    import_id: int,
    item: InventoryDumpItem,
    slot_index: int,
) -> None:
    stat_values = _load_item_stat_values(connection, item.item_id)
    columns = [
        "character_name",
        "slot",
        "slot_index",
        "item_id",
        "item_name",
        "raw_item_name",
        "normalized_item_name",
        "inventory_import_id",
        "server",
        "raw_location",
        "quantity",
        "slots",
        "is_starter_item",
        "is_augment",
        "augment_parent_location",
        *_ITEM_STAT_COLUMNS,
        "notes",
    ]
    values: dict[str, Any] = {
        "character_name": character_name,
        "slot": item.equipment_slot,
        "slot_index": slot_index,
        "item_id": item.item_id,
        "item_name": item.item_name,
        "raw_item_name": item.raw_item_name,
        "normalized_item_name": item.normalized_item_name,
        "inventory_import_id": import_id,
        "server": server,
        "raw_location": item.raw_location,
        "quantity": item.quantity,
        "slots": item.slots,
        "is_starter_item": int(item.is_starter_item),
        "is_augment": int(item.is_augment),
        "augment_parent_location": item.augment_parent_location,
        "notes": f"Imported from inventory dump location {item.raw_location}",
    }
    values.update(stat_values)
    placeholders = ", ".join("?" for _ in columns)
    connection.execute(
        f"""
        INSERT INTO character_equipment ({", ".join(columns)})
        VALUES ({placeholders})
        """,
        tuple(values[column] for column in columns),
    )


def _load_item_stat_values(connection: sqlite3.Connection, item_id: int) -> dict[str, Any]:
    row = connection.execute(
        f"SELECT {', '.join(_ITEM_STAT_COLUMNS)} FROM items WHERE item_id = ?",
        (item_id,),
    ).fetchone()
    if row is None:
        return {column: None for column in _ITEM_STAT_COLUMNS}
    return {column: row[index] for index, column in enumerate(_ITEM_STAT_COLUMNS)}


def _insert_character_inventory_item(
    connection: sqlite3.Connection,
    character_name: str,
    server: str,
    import_id: int,
    item: InventoryDumpItem,
) -> None:
    connection.execute(
        """
        INSERT INTO character_inventory_items (
            character_name, server, inventory_import_id, area, raw_location,
            parent_location, location_index, location_slot_index, item_id,
            item_name, raw_item_name, normalized_item_name, quantity, slots,
            is_container, is_starter_item, is_augment, augment_parent_location
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            character_name,
            server,
            import_id,
            item.area,
            item.raw_location,
            item.parent_location,
            item.location_index,
            item.location_slot_index,
            item.item_id,
            item.item_name,
            item.raw_item_name,
            item.normalized_item_name,
            item.quantity,
            item.slots,
            int(item.is_container),
            int(item.is_starter_item),
            int(item.is_augment),
            item.augment_parent_location,
        ),
    )


def _enqueue_inventory_item_for_enrichment(connection: sqlite3.Connection, item: InventoryDumpItem) -> bool:
    if _item_source_primary(connection, item.item_id) == "lucy":
        return False

    cursor = connection.execute(
        """
        INSERT INTO pending_items (
            normalized_name, display_name, last_raw_line
        ) VALUES (?, ?, ?)
        ON CONFLICT(normalized_name) DO UPDATE SET
            display_name = excluded.display_name,
            last_seen_at = CURRENT_TIMESTAMP,
            seen_count = seen_count + 1,
            last_raw_line = excluded.last_raw_line
        """,
        (item.normalized_item_name, item.item_name, f"inventory:{item.raw_location}"),
    )
    return cursor.rowcount > 0


def _item_source_primary(connection: sqlite3.Connection, item_id: int) -> str | None:
    row = connection.execute("SELECT source_primary FROM items WHERE item_id = ?", (item_id,)).fetchone()
    return str(row[0]) if row and row[0] is not None else None


def _finalize_inventory_import(connection: sqlite3.Connection, import_id: int, stats: InventoryImportStats) -> None:
    connection.execute(
        """
        UPDATE inventory_imports
        SET equipment_items_imported = ?, inventory_items_imported = ?
        WHERE inventory_import_id = ?
        """,
        (stats.equipment_items_imported, stats.inventory_items_imported, import_id),
    )


def _record_inventory_import_run(connection: sqlite3.Connection, stats: InventoryImportStats) -> None:
    connection.execute(
        """
        INSERT INTO import_runs (
            source_name, source_url, status, items_seen, items_inserted,
            items_updated, finished_at
        ) VALUES ('inventory_dump', ?, 'completed', ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            f"file={stats.source_file};character={stats.character_name};server={stats.server};hash={stats.source_hash}",
            stats.rows_seen,
            stats.item_stubs_upserted,
            stats.rows_imported,
        ),
    )

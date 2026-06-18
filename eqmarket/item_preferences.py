from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Literal

from eqmarket.log_parser import normalize_item_name


ItemPreferenceStatus = Literal["wanted", "ignored"]
ItemPreferenceStatusUpdate = Literal["wanted", "ignored", "neutral"]
ItemPreferenceKeyKind = Literal["item_id", "name"]

ITEM_PREFERENCE_STATUSES = {"wanted", "ignored"}
NEUTRAL_ITEM_PREFERENCE_STATUS = "neutral"


@dataclass(frozen=True)
class ItemPreferenceTarget:
    server: str
    preference_key_kind: ItemPreferenceKeyKind
    preference_key: str
    item_id: int | None
    item_name: str
    normalized_item_name: str


def fetch_item_preference_target(
    connection: sqlite3.Connection,
    server: str,
    item_id: int,
) -> ItemPreferenceTarget | None:
    row = connection.execute(
        """
        SELECT item_id, name, normalized_name
        FROM items
        WHERE item_id = ?
        """,
        (item_id,),
    ).fetchone()
    if row is None:
        return None

    return ItemPreferenceTarget(
        server=server.lower(),
        preference_key_kind="item_id",
        preference_key=str(int(row["item_id"])),
        item_id=int(row["item_id"]),
        item_name=str(row["name"]),
        normalized_item_name=str(row["normalized_name"]),
    )


def fetch_listing_preference_target(
    connection: sqlite3.Connection,
    listing_id: int,
) -> ItemPreferenceTarget | None:
    row = connection.execute(
        """
        SELECT
            ml.server,
            ml.item_id,
            ml.item_name AS listed_item_name,
            ml.normalized_item_name AS listed_normalized_item_name,
            i.name AS canonical_item_name,
            i.normalized_name AS canonical_normalized_item_name
        FROM market_listings ml
        LEFT JOIN items i
            ON i.item_id = ml.item_id
        WHERE ml.listing_id = ?
        """,
        (listing_id,),
    ).fetchone()
    if row is None:
        return None

    item_id = _optional_int(row["item_id"])
    item_name = row["canonical_item_name"] or row["listed_item_name"]
    normalized_item_name = (
        row["canonical_normalized_item_name"]
        or row["listed_normalized_item_name"]
        or normalize_item_name(str(item_name))
    )

    if item_id is not None:
        preference_key_kind: ItemPreferenceKeyKind = "item_id"
        preference_key = str(item_id)
    else:
        preference_key_kind = "name"
        preference_key = normalized_item_name

    return ItemPreferenceTarget(
        server=str(row["server"]).lower(),
        preference_key_kind=preference_key_kind,
        preference_key=preference_key,
        item_id=item_id,
        item_name=str(item_name),
        normalized_item_name=str(normalized_item_name),
    )


def set_item_preference(
    connection: sqlite3.Connection,
    target: ItemPreferenceTarget,
    status: ItemPreferenceStatusUpdate,
    *,
    notes: str | None = None,
) -> dict[str, Any]:
    if status == NEUTRAL_ITEM_PREFERENCE_STATUS:
        connection.execute(
            """
            DELETE FROM item_preferences
            WHERE server = ?
              AND preference_key_kind = ?
              AND preference_key = ?
            """,
            (target.server, target.preference_key_kind, target.preference_key),
        )
        return _neutral_preference_payload(target)

    if status not in ITEM_PREFERENCE_STATUSES:
        raise ValueError(f"Unsupported item preference status: {status}")

    connection.execute(
        """
        INSERT INTO item_preferences (
            server,
            preference_key_kind,
            preference_key,
            item_id,
            item_name,
            normalized_item_name,
            status,
            notes,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(server, preference_key_kind, preference_key) DO UPDATE SET
            item_id = excluded.item_id,
            item_name = excluded.item_name,
            normalized_item_name = excluded.normalized_item_name,
            status = excluded.status,
            notes = excluded.notes,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            target.server,
            target.preference_key_kind,
            target.preference_key,
            target.item_id,
            target.item_name,
            target.normalized_item_name,
            status,
            notes,
        ),
    )

    row = connection.execute(
        """
        SELECT
            preference_id,
            server,
            preference_key_kind,
            preference_key,
            item_id,
            item_name,
            normalized_item_name,
            status,
            notes,
            created_at,
            updated_at
        FROM item_preferences
        WHERE server = ?
          AND preference_key_kind = ?
          AND preference_key = ?
        """,
        (target.server, target.preference_key_kind, target.preference_key),
    ).fetchone()
    if row is None:
        raise sqlite3.DatabaseError("Item preference write did not return a row")
    return item_preference_payload(row)


def fetch_item_preferences(
    connection: sqlite3.Connection,
    server: str,
    *,
    status: ItemPreferenceStatus | None = None,
) -> list[dict[str, Any]]:
    params: list[Any] = [server.lower()]
    status_filter = ""

    if status is not None:
        status_filter = "AND status = ?"
        params.append(status)

    rows = connection.execute(
        f"""
        SELECT
            preference_id,
            server,
            preference_key_kind,
            preference_key,
            item_id,
            item_name,
            normalized_item_name,
            status,
            notes,
            created_at,
            updated_at
        FROM item_preferences
        WHERE server = ?
          {status_filter}
        ORDER BY status, item_name COLLATE NOCASE
        """,
        params,
    ).fetchall()

    return [item_preference_payload(row) for row in rows]


def item_preference_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "preference_id": int(row["preference_id"]),
        "server": row["server"],
        "preference_key_kind": row["preference_key_kind"],
        "preference_key": row["preference_key"],
        "item_id": _optional_int(row["item_id"]),
        "item_name": row["item_name"],
        "normalized_item_name": row["normalized_item_name"],
        "status": row["status"],
        "notes": row["notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _neutral_preference_payload(target: ItemPreferenceTarget) -> dict[str, Any]:
    return {
        "preference_id": None,
        "server": target.server,
        "preference_key_kind": target.preference_key_kind,
        "preference_key": target.preference_key,
        "item_id": target.item_id,
        "item_name": target.item_name,
        "normalized_item_name": target.normalized_item_name,
        "status": NEUTRAL_ITEM_PREFERENCE_STATUS,
        "notes": None,
        "created_at": None,
        "updated_at": None,
    }


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)

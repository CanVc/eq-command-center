from __future__ import annotations

import sqlite3
from typing import Any


def fetch_item_sources(connection: sqlite3.Connection, item_id: int) -> list[dict[str, Any]]:
    return fetch_item_sources_by_id(connection, [item_id]).get(item_id, [])


def fetch_item_sources_by_id(
    connection: sqlite3.Connection,
    item_ids: list[int] | set[int] | tuple[int, ...],
) -> dict[int, list[dict[str, Any]]]:
    unique_item_ids = sorted({int(item_id) for item_id in item_ids if item_id is not None})
    if not unique_item_ids:
        return {}

    placeholders = ", ".join("?" for _ in unique_item_ids)
    rows = connection.execute(
        f"""
        SELECT
            item_id,
            data_source,
            source_url,
            external_item_id,
            content_type,
            zone,
            source_area,
            npc_name,
            last_checked_at,
            confidence
        FROM item_sources
        WHERE item_id IN ({placeholders})
        ORDER BY
            CASE WHEN zone IS NULL AND npc_name IS NULL THEN 1 ELSE 0 END,
            lower(COALESCE(zone, '')),
            lower(COALESCE(npc_name, '')),
            lower(data_source),
            COALESCE(source_url, '')
        """,
        unique_item_ids,
    ).fetchall()

    sources_by_item_id: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        sources_by_item_id.setdefault(int(row["item_id"]), []).append(_item_source_payload(row))
    return sources_by_item_id


def _item_source_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "item_id": int(row["item_id"]),
        "data_source": row["data_source"],
        "source_url": row["source_url"],
        "external_item_id": row["external_item_id"],
        "content_type": row["content_type"],
        "zone": row["zone"],
        "source_area": row["source_area"],
        "npc_name": row["npc_name"],
        "last_checked_at": row["last_checked_at"],
        "confidence": row["confidence"],
    }

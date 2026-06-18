from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class ItemCandidate:
    item_id: int
    name: str
    slot: str | None
    classes: str | None
    item_type: str | None
    tlp_market_price_pp: int | None
    has_tlp_price: bool
    has_manual_override: bool


def load_item_candidates(
    connection: sqlite3.Connection,
    normalized_name: str,
    *,
    server: str | None = None,
) -> list[ItemCandidate]:
    """Return local item rows sharing an exact normalized display name."""
    if server is None:
        rows = connection.execute(
            """
            SELECT item_id, name, slot, classes, item_type,
                   NULL AS tlp_market_price_pp,
                   0 AS has_tlp_price,
                   0 AS has_manual_override
            FROM items
            WHERE normalized_name = ?
            ORDER BY item_id
            """,
            (normalized_name,),
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT
                i.item_id,
                i.name,
                i.slot,
                i.classes,
                i.item_type,
                COALESCE(NULLIF(mp.median_pp, 0), NULLIF(mp.avg_pp, 0), NULLIF(mp.p25_pp, 0)) AS tlp_market_price_pp,
                CASE
                    WHEN COALESCE(NULLIF(mp.median_pp, 0), NULLIF(mp.avg_pp, 0), NULLIF(mp.p25_pp, 0)) IS NOT NULL
                         AND (
                            mp.source = 'tlp_auctions_history'
                            OR mp.source = 'tlp_auctions_catalog'
                            OR mp.source LIKE 'tlp_auctions_%'
                         )
                    THEN 1 ELSE 0
                END AS has_tlp_price,
                CASE WHEN mpo.item_id IS NOT NULL THEN 1 ELSE 0 END AS has_manual_override
            FROM items i
            LEFT JOIN market_prices mp
                ON mp.item_id = i.item_id AND lower(mp.server) = lower(?)
            LEFT JOIN market_prices_override mpo
                ON mpo.item_id = i.item_id AND lower(mpo.server) = lower(?)
            WHERE i.normalized_name = ?
            ORDER BY i.item_id
            """,
            (server, server, normalized_name),
        ).fetchall()

    return [
        ItemCandidate(
            item_id=int(row[0]),
            name=str(row[1]),
            slot=row[2],
            classes=row[3],
            item_type=row[4],
            tlp_market_price_pp=_optional_int(row[5]),
            has_tlp_price=bool(row[6]),
            has_manual_override=bool(row[7]),
        )
        for row in rows
    ]


def resolve_item_id_for_listing(
    connection: sqlite3.Connection,
    server: str,
    normalized_name: str,
    *,
    exact_item_id: int | None = None,
) -> int | None:
    """Choose the best single local item_id for a name-only market listing.

    Resolution order:
    1. Preserve an exact item link when the linked id exists for the same name.
    2. Use the only candidate with a manual override, if present.
    3. Use the only candidate with a positive TLP Auctions price/history.
    4. If several candidates have TLP prices, choose the lowest positive price
       to avoid optimistic deal scoring, with item_id as a deterministic tie-breaker.
    5. For equipable variants without prices, prefer the largest item_id.
    6. Otherwise leave the listing unresolved.
    """
    candidates = load_item_candidates(connection, normalized_name, server=server)
    if not candidates:
        return None

    if exact_item_id is not None:
        for candidate in candidates:
            if candidate.item_id == exact_item_id:
                return exact_item_id

    if len(candidates) == 1:
        return candidates[0].item_id

    manual_candidates = [candidate for candidate in candidates if candidate.has_manual_override]
    if len(manual_candidates) == 1:
        return manual_candidates[0].item_id

    tlp_priced_candidates = [candidate for candidate in candidates if candidate.has_tlp_price and candidate.tlp_market_price_pp]
    if len(tlp_priced_candidates) == 1:
        return tlp_priced_candidates[0].item_id
    if len(tlp_priced_candidates) > 1:
        return min(
            tlp_priced_candidates,
            key=lambda candidate: (candidate.tlp_market_price_pp or 0, candidate.item_id),
        ).item_id

    equipable_candidates = [candidate for candidate in candidates if _is_probably_equippable(candidate)]
    if equipable_candidates:
        return max(candidate.item_id for candidate in equipable_candidates)

    return None


def _is_probably_equippable(candidate: ItemCandidate) -> bool:
    text_fields = [candidate.slot, candidate.classes]
    return any(str(value).strip() for value in text_fields if value is not None)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from eqmarket.db import init_db
from eqmarket.log_parser import normalize_item_name
from eqmarket.sources.tlp_auctions import (
    CatalogItem,
    TlpAuctionsClient,
    TlpAuctionsError,
    compute_price_stats,
    db_server_name,
)


@dataclass
class TlpPriceImportStats:
    catalog_items_seen: int = 0
    items_upserted: int = 0
    listings_linked: int = 0
    catalog_prices_upserted: int = 0
    history_items_checked: int = 0
    history_prices_upserted: int = 0
    no_price_data: int = 0
    price_refresh_failed: int = 0
    krono_updated: bool = False
    krono_price_pp: int | None = None
    krono_listings_converted: int = 0


def import_tlp_prices(
    db_path: Path,
    server: str,
    *,
    limit: int | None = None,
    item_ids: list[int] | None = None,
    all_catalog: bool = False,
    fetch_history: bool = True,
    history_days: int | None = 3,
) -> TlpPriceImportStats:
    """Import TLP Auctions reference prices into market_prices.

    By default this targets known local item ids for the server (resolved log
    listings + watchlist). Use all_catalog=True to seed every catalog item that
    has a TLP Auctions item id/name.
    """
    init_db(db_path)
    stats = TlpPriceImportStats()
    client = TlpAuctionsClient()
    api_server = server
    db_server = db_server_name(server)

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        krono = client.get_krono_price(api_server)
        if krono is not None:
            stats.krono_price_pp = round(krono.average_price)
            _upsert_krono_price(connection, db_server, stats.krono_price_pp, krono.sample_size, krono.last_updated)
            stats.krono_updated = True
            stats.krono_listings_converted = _convert_krono_listings(connection, db_server, stats.krono_price_pp)

        catalog = client.get_catalog(api_server)
        stats.catalog_items_seen = len(catalog)
        catalog_by_id = {item.item_id: item for item in catalog}

        wanted_normalized_names = _load_wanted_normalized_names(connection, db_server)
        explicit_item_ids = set(item_ids or [])
        matched_catalog = [
            item
            for item in catalog
            if all_catalog
            or item.item_id in explicit_item_ids
            or normalize_item_name(item.name) in wanted_normalized_names
        ]

        for item in matched_catalog:
            if _upsert_minimal_item(connection, item):
                stats.items_upserted += 1
            stats.listings_linked += _link_listings_by_name(connection, db_server, item)

        target_item_ids = _load_target_item_ids(connection, db_server, item_ids)
        if all_catalog:
            target_item_ids.update(item.item_id for item in catalog)
        target_item_ids = {item_id for item_id in target_item_ids if _item_exists(connection, item_id)}
        if limit is not None:
            target_item_ids = set(sorted(target_item_ids)[:limit])

        for item_id in sorted(target_item_ids):
            item = catalog_by_id.get(item_id)
            if not fetch_history:
                if item is not None and item.price is not None and item.price > 0:
                    _upsert_catalog_price(connection, db_server, item)
                    stats.catalog_prices_upserted += 1
                else:
                    stats.no_price_data += 1
                continue

            stats.history_items_checked += 1
            try:
                points = client.get_item_history(item_id, api_server)
            except (OSError, TlpAuctionsError) as exc:
                stats.price_refresh_failed += 1
                _record_price_refresh_failure(connection, db_server, item_id, exc)
                continue

            price_stats = compute_price_stats(points, stats.krono_price_pp, max_age_days=history_days)
            if price_stats is None:
                _delete_tlp_market_price(connection, db_server, item_id)
                stats.no_price_data += 1
                continue
            _upsert_history_price(connection, db_server, item_id, price_stats)
            stats.history_prices_upserted += 1

        _record_tlp_price_import_run(connection, db_server, stats, fetch_history, history_days)

    return stats


def _upsert_minimal_item(connection: sqlite3.Connection, item: CatalogItem) -> bool:
    try:
        cursor = connection.execute(
            """
            INSERT INTO items (
                item_id, name, normalized_name, source_primary, raw_payload,
                parser_version, last_imported_at, updated_at
            ) VALUES (?, ?, ?, 'tlp_auctions', ?, 'tlp_auctions_v3', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(item_id) DO UPDATE SET
                source_primary = COALESCE(items.source_primary, excluded.source_primary),
                last_imported_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                item.item_id,
                item.name,
                normalize_item_name(item.name),
                json.dumps({"source": "tlp_auctions_catalog", "price": item.price}, ensure_ascii=False, sort_keys=True),
            ),
        )
    except sqlite3.IntegrityError:
        # TLP catalog can contain duplicate normalized names with different ids.
        # Keep the first item already present because items.normalized_name is canonical locally.
        return False
    return cursor.rowcount > 0


def _item_exists(connection: sqlite3.Connection, item_id: int) -> bool:
    row = connection.execute("SELECT 1 FROM items WHERE item_id = ?", (item_id,)).fetchone()
    return row is not None


def _upsert_krono_price(
    connection: sqlite3.Connection,
    db_server: str,
    price_pp: int,
    sample_size: int,
    last_updated: str | None,
) -> None:
    connection.execute(
        """
        INSERT INTO krono_prices (server, price_pp, source, confidence, last_refresh_at)
        VALUES (?, ?, 'tlp_auctions', ?, COALESCE(?, CURRENT_TIMESTAMP))
        ON CONFLICT(server) DO UPDATE SET
            price_pp = excluded.price_pp,
            source = excluded.source,
            confidence = excluded.confidence,
            last_refresh_at = excluded.last_refresh_at
        """,
        (db_server, price_pp, _sample_confidence(sample_size), last_updated),
    )


def _convert_krono_listings(connection: sqlite3.Connection, db_server: str, krono_price_pp: int) -> int:
    cursor = connection.execute(
        """
        UPDATE market_listings
        SET price_pp = CAST(ROUND(price_amount * ?) AS INTEGER),
            krono_price_pp_used = ?
        WHERE lower(server) = ?
          AND lower(COALESCE(price_currency, '')) = 'krono'
          AND price_amount IS NOT NULL
        """,
        (krono_price_pp, krono_price_pp, db_server),
    )
    return cursor.rowcount


def _upsert_catalog_price(connection: sqlite3.Connection, db_server: str, item: CatalogItem) -> None:
    median_pp = round(item.price or 0)
    raw_payload = json.dumps(
        {"source": "tlp_auctions_catalog", "price": item.price},
        ensure_ascii=False,
        sort_keys=True,
    )
    connection.execute(
        """
        INSERT INTO market_prices (
            item_id, server, median_pp, avg_pp, sample_size, confidence,
            last_refresh_at, source, raw_payload
        ) VALUES (?, ?, ?, ?, NULL, 'catalog', CURRENT_TIMESTAMP, 'tlp_auctions_catalog', ?)
        ON CONFLICT(item_id, server) DO UPDATE SET
            median_pp = excluded.median_pp,
            avg_pp = excluded.avg_pp,
            confidence = excluded.confidence,
            last_refresh_at = excluded.last_refresh_at,
            source = excluded.source,
            raw_payload = excluded.raw_payload
        """,
        (item.item_id, db_server, median_pp, median_pp, raw_payload),
    )


def _record_tlp_price_import_run(
    connection: sqlite3.Connection,
    db_server: str,
    stats: TlpPriceImportStats,
    fetch_history: bool,
    history_days: int | None,
) -> None:
    status = "completed_with_errors" if stats.price_refresh_failed else "completed"
    source_url = (
        f"server={db_server};mode=history;history_days={history_days}"
        if fetch_history
        else f"server={db_server};mode=catalog"
    )
    error = f"price_refresh_failed={stats.price_refresh_failed}" if stats.price_refresh_failed else None
    connection.execute(
        """
        INSERT INTO import_runs (
            source_name, source_url, status, items_seen, items_inserted,
            items_updated, error, finished_at
        ) VALUES ('tlp_auctions_prices', ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            source_url,
            status,
            stats.catalog_items_seen,
            stats.items_upserted,
            stats.catalog_prices_upserted + stats.history_prices_upserted + stats.krono_listings_converted,
            error,
        ),
    )


def _record_price_refresh_failure(
    connection: sqlite3.Connection,
    db_server: str,
    item_id: int,
    exc: Exception,
) -> None:
    connection.execute(
        """
        INSERT INTO import_runs (source_name, source_url, status, error, finished_at)
        VALUES ('tlp_auctions_history', ?, 'failed', ?, CURRENT_TIMESTAMP)
        """,
        (f"item_id={item_id};server={db_server}", str(exc)[:1000]),
    )


def _delete_tlp_market_price(connection: sqlite3.Connection, db_server: str, item_id: int) -> None:
    connection.execute(
        """
        DELETE FROM market_prices
        WHERE item_id = ?
          AND lower(server) = ?
          AND source LIKE 'tlp_auctions%'
        """,
        (item_id, db_server),
    )


def _upsert_history_price(connection: sqlite3.Connection, db_server: str, item_id: int, stats) -> None:
    connection.execute(
        """
        INSERT INTO market_prices (
            item_id, server, median_pp, p25_pp, p75_pp, avg_pp, min_pp, max_pp,
            sample_size, confidence, last_refresh_at, source, raw_payload
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 'tlp_auctions_history', ?)
        ON CONFLICT(item_id, server) DO UPDATE SET
            median_pp = excluded.median_pp,
            p25_pp = excluded.p25_pp,
            p75_pp = excluded.p75_pp,
            avg_pp = excluded.avg_pp,
            min_pp = excluded.min_pp,
            max_pp = excluded.max_pp,
            sample_size = excluded.sample_size,
            confidence = excluded.confidence,
            last_refresh_at = excluded.last_refresh_at,
            source = excluded.source,
            raw_payload = excluded.raw_payload
        """,
        (
            item_id,
            db_server,
            stats.median_pp,
            stats.p25_pp,
            stats.p75_pp,
            stats.avg_pp,
            stats.min_pp,
            stats.max_pp,
            stats.sample_size,
            stats.confidence,
            stats.raw_payload,
        ),
    )


def _load_wanted_normalized_names(connection: sqlite3.Connection, db_server: str) -> set[str]:
    rows = connection.execute(
        """
        SELECT normalized_item_name
        FROM market_listings
        WHERE lower(server) = ? AND item_id IS NULL AND normalized_item_name IS NOT NULL
        UNION
        SELECT normalized_item_name
        FROM watchlist_items
        WHERE lower(server) = ? AND item_id IS NULL AND normalized_item_name IS NOT NULL
        """,
        (db_server, db_server),
    ).fetchall()
    return {str(row[0]) for row in rows if row[0]}


def _load_target_item_ids(connection: sqlite3.Connection, db_server: str, item_ids: list[int] | None) -> set[int]:
    if item_ids is not None:
        return set(item_ids)
    rows = connection.execute(
        """
        SELECT item_id
        FROM market_listings
        WHERE lower(server) = ? AND item_id IS NOT NULL
        UNION
        SELECT item_id
        FROM watchlist_items
        WHERE lower(server) = ? AND item_id IS NOT NULL
        """,
        (db_server, db_server),
    ).fetchall()
    return {int(row[0]) for row in rows if row[0] is not None}


def _link_listings_by_name(connection: sqlite3.Connection, db_server: str, item: CatalogItem) -> int:
    normalized_name = normalize_item_name(item.name)
    cursor = connection.execute(
        """
        UPDATE market_listings
        SET item_id = ?
        WHERE lower(server) = ?
          AND item_id IS NULL
          AND normalized_item_name = ?
        """,
        (item.item_id, db_server, normalized_name),
    )
    linked = cursor.rowcount
    connection.execute(
        """
        UPDATE watchlist_items
        SET item_id = ?, updated_at = CURRENT_TIMESTAMP
        WHERE lower(server) = ?
          AND item_id IS NULL
          AND normalized_item_name = ?
        """,
        (item.item_id, db_server, normalized_name),
    )
    return linked


def _sample_confidence(sample_size: int) -> str:
    if sample_size >= 20:
        return "high"
    if sample_size >= 5:
        return "medium"
    if sample_size >= 1:
        return "low"
    return "none"

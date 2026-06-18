from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from eqmarket.db import init_db
from eqmarket.item_resolution import load_item_candidates, resolve_item_id_for_listing
from eqmarket.log_parser import normalize_item_name
from eqmarket.review_rules import apply_active_discard_rules
from eqmarket.sources.tlp_auctions import (
    CatalogItem,
    PriceStats,
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


@dataclass(frozen=True)
class _HistoryPriceRefreshTarget:
    item_id: int
    tlp_item_id: int


@dataclass(frozen=True)
class _HistoryPriceRefreshResult:
    item_id: int
    tlp_item_id: int
    price_stats: PriceStats | None = None
    error: Exception | None = None


PriceImportProgressCallback = Callable[[dict[str, object]], None]

TLP_MARKET_PRICE_SOURCES = (
    "tlp_auctions",
    "tlp_auctions_catalog",
    "tlp_auctions_history",
    "tlp_auctions_history_no_data",
    "tlp_auctions_history_failed",
)


def refresh_krono_price(db_path: Path, server: str) -> TlpPriceImportStats:
    """Refresh only the cached Krono price for a server from TLP Auctions."""
    init_db(db_path)
    stats = TlpPriceImportStats()
    client = TlpAuctionsClient()
    api_server = server
    db_server = db_server_name(server)

    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        krono = client.get_krono_price(api_server)
        if krono is not None:
            stats.krono_price_pp = round(krono.average_price)
            _upsert_krono_price(connection, db_server, stats.krono_price_pp, krono.sample_size, krono.last_updated)
            stats.krono_updated = True
            stats.krono_listings_converted = _convert_krono_listings(connection, db_server, stats.krono_price_pp)
            apply_active_discard_rules(connection, db_server)
        connection.commit()

    return stats


def load_recent_listing_item_ids(
    db_path: Path,
    server: str,
    limit: int,
    *,
    max_age_hours: float | None = None,
) -> list[int]:
    """Return recent listing item ids, optionally only missing/stale TLP prices."""
    db_server = db_server_name(server)
    freshness_filter, freshness_params = _stale_price_filter(max_age_hours)
    params: list[object] = [db_server, *freshness_params, limit]

    with closing(sqlite3.connect(db_path)) as connection:
        rows = connection.execute(
            f"""
            SELECT ml.item_id
            FROM market_listings ml
            LEFT JOIN market_prices mp
                ON mp.item_id = ml.item_id AND lower(mp.server) = lower(ml.server)
            WHERE lower(ml.server) = ?
              AND ml.item_id IS NOT NULL
              AND ml.price_pp IS NOT NULL
{freshness_filter}
            GROUP BY ml.item_id
            ORDER BY max(ml.timestamp) DESC, max(ml.listing_id) DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [int(row[0]) for row in rows]


def mark_tlp_prices_stale(db_path: Path, server: str) -> int:
    """Invalidate cached TLP market_prices for one server without touching manual overrides."""
    init_db(db_path)
    db_server = db_server_name(server)

    with closing(sqlite3.connect(db_path)) as connection:
        source_placeholders = ", ".join("?" for _ in TLP_MARKET_PRICE_SOURCES)
        cursor = connection.execute(
            f"""
            UPDATE market_prices
            SET last_refresh_at = NULL
            WHERE lower(server) = ?
              AND (
                    source IN ({source_placeholders})
                    OR source LIKE 'tlp_auctions_%'
                    OR raw_payload LIKE '%tlp_auctions%'
                  )
            """,
            [db_server, *TLP_MARKET_PRICE_SOURCES],
        )
        affected_count = cursor.rowcount
        connection.commit()
    return affected_count


def count_unresolved_priced_listing_names(db_path: Path, server: str) -> int:
    """Return unresolved priced listing/watchlist names that TLP catalog matching can resolve."""
    db_server = db_server_name(server)
    with closing(sqlite3.connect(db_path)) as connection:
        row = connection.execute(
            """
            SELECT count(*)
            FROM (
                SELECT normalized_item_name
                FROM market_listings
                WHERE lower(server) = ?
                  AND item_id IS NULL
                  AND normalized_item_name IS NOT NULL
                  AND price_pp IS NOT NULL
                GROUP BY normalized_item_name
                UNION
                SELECT normalized_item_name
                FROM watchlist_items
                WHERE lower(server) = ?
                  AND item_id IS NULL
                  AND normalized_item_name IS NOT NULL
                  AND enabled = 1
                GROUP BY normalized_item_name
            ) unresolved_names
            """,
            (db_server, db_server),
        ).fetchone()
    return int(row[0]) if row else 0


def count_stale_listing_item_ids(
    db_path: Path,
    server: str,
    *,
    max_age_hours: float | None = None,
) -> int:
    """Return the approximate number of local listing item ids needing TLP price refresh."""
    db_server = db_server_name(server)
    freshness_filter, freshness_params = _stale_price_filter(max_age_hours)
    params: list[object] = [db_server, *freshness_params]

    with closing(sqlite3.connect(db_path)) as connection:
        row = connection.execute(
            f"""
            SELECT count(*)
            FROM (
                SELECT ml.item_id
                FROM market_listings ml
                LEFT JOIN market_prices mp
                    ON mp.item_id = ml.item_id AND lower(mp.server) = lower(ml.server)
                WHERE lower(ml.server) = ?
                  AND ml.item_id IS NOT NULL
                  AND ml.price_pp IS NOT NULL
{freshness_filter}
                GROUP BY ml.item_id
            ) stale_items
            """,
            params,
        ).fetchone()
    return int(row[0]) if row else 0


def _stale_price_filter(max_age_hours: float | None) -> tuple[str, list[object]]:
    if max_age_hours is None:
        return "", []
    return (
        """
              AND (
                    mp.item_id IS NULL
                    OR mp.confidence = 'failed'
                    OR mp.source = 'tlp_auctions_history_failed'
                    OR mp.last_refresh_at IS NULL
                    OR datetime(mp.last_refresh_at) <= datetime('now', ?)
                  )
        """,
        [f"-{max_age_hours:g} hours"],
    )


def import_tlp_prices(
    db_path: Path,
    server: str,
    *,
    limit: int | None = None,
    item_ids: Iterable[int] | None = None,
    all_catalog: bool = False,
    fetch_history: bool = True,
    history_days: int | None = 3,
    progress_callback: PriceImportProgressCallback | None = None,
    concurrency: int = 1,
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
    item_id_list = list(item_ids) if item_ids is not None else None

    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        _notify_price_import_progress(progress_callback, phase="krono", completed=0, total=None)
        krono = client.get_krono_price(api_server)
        if krono is not None:
            stats.krono_price_pp = round(krono.average_price)
            _upsert_krono_price(connection, db_server, stats.krono_price_pp, krono.sample_size, krono.last_updated)
            stats.krono_updated = True
            stats.krono_listings_converted = _convert_krono_listings(connection, db_server, stats.krono_price_pp)
            apply_active_discard_rules(connection, db_server)

        _notify_price_import_progress(progress_callback, phase="catalog", completed=0, total=None)
        catalog = client.get_catalog(api_server)
        stats.catalog_items_seen = len(catalog)
        catalog_by_id = {item.item_id: item for item in catalog}
        catalog_by_normalized_name = _catalog_by_normalized_name(catalog)

        wanted_normalized_names = _load_wanted_normalized_names(connection, db_server)
        explicit_item_ids = set(item_id_list or [])
        initial_target_item_ids = _load_target_item_ids(connection, db_server, item_id_list)
        target_normalized_names = _load_normalized_names_for_item_ids(connection, initial_target_item_ids)
        relevant_normalized_names = wanted_normalized_names | set(target_normalized_names.values())

        matched_catalog = [
            item
            for item in catalog
            if all_catalog
            or item.item_id in explicit_item_ids
            or normalize_item_name(item.name) in relevant_normalized_names
        ]

        for item in matched_catalog:
            if _upsert_minimal_item(connection, item):
                stats.items_upserted += 1

        target_item_ids = _expand_target_item_ids(
            connection,
            catalog_by_normalized_name,
            initial_target_item_ids,
            relevant_normalized_names,
            all_catalog=all_catalog,
        )
        target_item_ids = {item_id for item_id in target_item_ids if _item_exists(connection, item_id)}
        if limit is not None:
            target_item_ids = set(sorted(target_item_ids)[:limit])

        sorted_target_item_ids = sorted(target_item_ids)
        progress_phase = "history" if fetch_history else "catalog_prices"

        if fetch_history:
            history_targets = _build_history_refresh_targets(
                connection,
                catalog_by_normalized_name,
                sorted_target_item_ids,
            )
            _notify_price_import_progress(
                progress_callback,
                phase=progress_phase,
                completed=0,
                total=len(history_targets),
            )
            _refresh_history_prices(
                connection,
                client,
                db_server,
                api_server,
                history_targets,
                stats.krono_price_pp,
                history_days,
                max(1, concurrency),
                stats,
                progress_callback,
                progress_phase,
            )
        else:
            _notify_price_import_progress(
                progress_callback,
                phase=progress_phase,
                completed=0,
                total=len(sorted_target_item_ids),
            )
            for completed, item_id in enumerate(sorted_target_item_ids, start=1):
                item = catalog_by_id.get(item_id)
                if item is not None and item.price is not None and item.price > 0:
                    _upsert_catalog_price(connection, db_server, item)
                    stats.catalog_prices_upserted += 1
                else:
                    stats.no_price_data += 1
                _notify_price_import_progress(
                    progress_callback,
                    phase=progress_phase,
                    completed=completed,
                    total=len(sorted_target_item_ids),
                    item_id=item_id,
                )

        refreshed_names = relevant_normalized_names | set(
            _load_normalized_names_for_item_ids(connection, target_item_ids).values()
        )
        for normalized_name in sorted(refreshed_names):
            stats.listings_linked += _link_listings_by_name(connection, db_server, normalized_name)

        apply_active_discard_rules(connection, db_server)

        _record_tlp_price_import_run(connection, db_server, stats, fetch_history, history_days)
        connection.commit()

    return stats


def _refresh_history_prices(
    connection: sqlite3.Connection,
    client: TlpAuctionsClient,
    db_server: str,
    api_server: str,
    targets: list[_HistoryPriceRefreshTarget],
    krono_price_pp: int | None,
    history_days: int | None,
    concurrency: int,
    stats: TlpPriceImportStats,
    progress_callback: PriceImportProgressCallback | None,
    progress_phase: str,
) -> None:
    total = len(targets)
    if total == 0:
        return

    if concurrency <= 1 or total == 1:
        results = (
            _fetch_history_price_stats(client, target, api_server, krono_price_pp, history_days)
            for target in targets
        )
        for completed, result in enumerate(results, start=1):
            _record_history_refresh_result(
                connection,
                db_server,
                result,
                stats,
                progress_callback,
                progress_phase,
                completed,
                total,
            )
        return

    max_workers = min(concurrency, total)
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="tlp-item-history") as executor:
        futures = {
            executor.submit(_fetch_history_price_stats, client, target, api_server, krono_price_pp, history_days): target
            for target in targets
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            target = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = _HistoryPriceRefreshResult(
                    item_id=target.item_id,
                    tlp_item_id=target.tlp_item_id,
                    error=exc,
                )
            _record_history_refresh_result(
                connection,
                db_server,
                result,
                stats,
                progress_callback,
                progress_phase,
                completed,
                total,
            )


def _fetch_history_price_stats(
    client: TlpAuctionsClient,
    target: _HistoryPriceRefreshTarget,
    api_server: str,
    krono_price_pp: int | None,
    history_days: int | None,
) -> _HistoryPriceRefreshResult:
    try:
        points = client.get_item_history(target.tlp_item_id, api_server)
    except (OSError, TlpAuctionsError) as exc:
        return _HistoryPriceRefreshResult(item_id=target.item_id, tlp_item_id=target.tlp_item_id, error=exc)

    price_stats = compute_price_stats(points, krono_price_pp, max_age_days=history_days)
    return _HistoryPriceRefreshResult(item_id=target.item_id, tlp_item_id=target.tlp_item_id, price_stats=price_stats)


def _record_history_refresh_result(
    connection: sqlite3.Connection,
    db_server: str,
    result: _HistoryPriceRefreshResult,
    stats: TlpPriceImportStats,
    progress_callback: PriceImportProgressCallback | None,
    progress_phase: str,
    completed: int,
    total: int,
) -> None:
    stats.history_items_checked += 1

    if result.error is not None:
        stats.price_refresh_failed += 1
        _record_price_refresh_failure(connection, db_server, result.item_id, result.tlp_item_id, result.error)
    elif result.price_stats is None:
        _upsert_price_refresh_marker(connection, db_server, result.item_id, "no_data", None, result.tlp_item_id)
        stats.no_price_data += 1
    else:
        _upsert_history_price(connection, db_server, result.item_id, result.price_stats, result.tlp_item_id)
        stats.history_prices_upserted += 1

    _notify_price_import_progress(
        progress_callback,
        phase=progress_phase,
        completed=completed,
        total=total,
        item_id=result.item_id,
        tlp_item_id=result.tlp_item_id,
    )


def _notify_price_import_progress(
    progress_callback: PriceImportProgressCallback | None,
    **payload: object,
) -> None:
    if progress_callback is None:
        return

    try:
        progress_callback(payload)
    except Exception:
        # Progress reporting must not make the import fail.
        return


def _upsert_minimal_item(connection: sqlite3.Connection, item: CatalogItem) -> bool:
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
    return cursor.rowcount > 0


def _item_exists(connection: sqlite3.Connection, item_id: int) -> bool:
    row = connection.execute("SELECT 1 FROM items WHERE item_id = ?", (item_id,)).fetchone()
    return row is not None


def _catalog_by_normalized_name(catalog: list[CatalogItem]) -> dict[str, list[CatalogItem]]:
    grouped: dict[str, list[CatalogItem]] = {}
    for item in catalog:
        grouped.setdefault(normalize_item_name(item.name), []).append(item)
    for items in grouped.values():
        items.sort(key=lambda catalog_item: catalog_item.item_id)
    return grouped


def _load_normalized_names_for_item_ids(
    connection: sqlite3.Connection,
    item_ids: set[int],
) -> dict[int, str]:
    if not item_ids:
        return {}
    result: dict[int, str] = {}
    sorted_item_ids = sorted(item_ids)
    for start in range(0, len(sorted_item_ids), 500):
        chunk = sorted_item_ids[start : start + 500]
        placeholders = ", ".join("?" for _ in chunk)
        rows = connection.execute(
            f"SELECT item_id, normalized_name FROM items WHERE item_id IN ({placeholders})",
            chunk,
        ).fetchall()
        result.update({int(row[0]): str(row[1]) for row in rows if row[1]})
    return result


def _load_item_ids_for_normalized_name(connection: sqlite3.Connection, normalized_name: str) -> set[int]:
    rows = connection.execute(
        "SELECT item_id FROM items WHERE normalized_name = ?",
        (normalized_name,),
    ).fetchall()
    return {int(row[0]) for row in rows}


def _expand_target_item_ids(
    connection: sqlite3.Connection,
    catalog_by_normalized_name: dict[str, list[CatalogItem]],
    initial_target_item_ids: set[int],
    relevant_normalized_names: set[str],
    *,
    all_catalog: bool,
) -> set[int]:
    target_item_ids = set(initial_target_item_ids)
    if all_catalog:
        for catalog_items in catalog_by_normalized_name.values():
            target_item_ids.update(item.item_id for item in catalog_items)

    for normalized_name in relevant_normalized_names:
        target_item_ids.update(_load_item_ids_for_normalized_name(connection, normalized_name))
        target_item_ids.update(item.item_id for item in catalog_by_normalized_name.get(normalized_name, []))
    return target_item_ids


def _build_history_refresh_targets(
    connection: sqlite3.Connection,
    catalog_by_normalized_name: dict[str, list[CatalogItem]],
    item_ids: list[int],
) -> list[_HistoryPriceRefreshTarget]:
    item_names = _load_normalized_names_for_item_ids(connection, set(item_ids))
    targets: dict[tuple[int, int], _HistoryPriceRefreshTarget] = {}

    for item_id in item_ids:
        normalized_name = item_names.get(item_id)
        catalog_items = catalog_by_normalized_name.get(normalized_name or "", [])
        catalog_item_ids = {item.item_id for item in catalog_items}
        for catalog_item in catalog_items:
            if _item_exists(connection, catalog_item.item_id):
                target = _HistoryPriceRefreshTarget(item_id=catalog_item.item_id, tlp_item_id=catalog_item.item_id)
                targets[(target.item_id, target.tlp_item_id)] = target

        # Also try the currently linked/local id when TLP's catalog uses a
        # different id. A 204/empty history will become a no_data marker, not a failure.
        if item_id not in catalog_item_ids:
            target = _HistoryPriceRefreshTarget(item_id=item_id, tlp_item_id=item_id)
            targets[(target.item_id, target.tlp_item_id)] = target

    return [targets[key] for key in sorted(targets)]


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
    tlp_item_id: int,
    exc: Exception,
) -> None:
    connection.execute(
        """
        INSERT INTO import_runs (source_name, source_url, status, error, finished_at)
        VALUES ('tlp_auctions_history', ?, 'failed', ?, CURRENT_TIMESTAMP)
        """,
        (f"item_id={item_id};tlp_item_id={tlp_item_id};server={db_server}", str(exc)[:1000]),
    )


def _upsert_price_refresh_marker(
    connection: sqlite3.Connection,
    db_server: str,
    item_id: int,
    status: str,
    error: str | None,
    tlp_item_id: int,
) -> None:
    raw_payload = json.dumps(
        {"source": "tlp_auctions_history", "status": status, "error": error, "tlp_item_id": tlp_item_id},
        ensure_ascii=False,
        sort_keys=True,
    )
    connection.execute(
        """
        INSERT INTO market_prices (
            item_id, server, median_pp, p25_pp, p75_pp, avg_pp, min_pp, max_pp,
            sample_size, confidence, last_refresh_at, source, raw_payload
        ) VALUES (?, ?, NULL, NULL, NULL, NULL, NULL, NULL, 0, ?, CURRENT_TIMESTAMP, ?, ?)
        ON CONFLICT(item_id, server) DO UPDATE SET
            median_pp = NULL,
            p25_pp = NULL,
            p75_pp = NULL,
            avg_pp = NULL,
            min_pp = NULL,
            max_pp = NULL,
            sample_size = 0,
            confidence = excluded.confidence,
            last_refresh_at = excluded.last_refresh_at,
            source = excluded.source,
            raw_payload = excluded.raw_payload
        """,
        (item_id, db_server, status, f"tlp_auctions_history_{status}", raw_payload),
    )


def _history_raw_payload_with_tlp_item_id(raw_payload: str, tlp_item_id: int) -> str:
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        payload = {"raw_payload": raw_payload}
    payload["tlp_item_id"] = tlp_item_id
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _upsert_history_price(
    connection: sqlite3.Connection,
    db_server: str,
    item_id: int,
    stats: PriceStats,
    tlp_item_id: int,
) -> None:
    raw_payload = _history_raw_payload_with_tlp_item_id(stats.raw_payload, tlp_item_id)
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
            raw_payload,
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


def _link_listings_by_name(
    connection: sqlite3.Connection,
    db_server: str,
    normalized_name: str,
) -> int:
    item_id = resolve_item_id_for_listing(connection, db_server, normalized_name)
    if item_id is None:
        return 0

    candidate_ids = [candidate.item_id for candidate in load_item_candidates(connection, normalized_name, server=db_server)]
    if not candidate_ids:
        return 0

    candidate_placeholders = ", ".join("?" for _ in candidate_ids)
    cursor = connection.execute(
        f"""
        UPDATE market_listings
        SET item_id = ?
        WHERE lower(server) = ?
          AND normalized_item_name = ?
          AND (
                item_id IS NULL
                OR (
                    item_id IN ({candidate_placeholders})
                    AND item_id != ?
                    AND NOT EXISTS (
                        SELECT 1
                        FROM market_prices_override mpo
                        WHERE mpo.item_id = market_listings.item_id
                          AND lower(mpo.server) = ?
                    )
                )
              )
        """,
        (item_id, db_server, normalized_name, *candidate_ids, item_id, db_server),
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
        (item_id, db_server, normalized_name),
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

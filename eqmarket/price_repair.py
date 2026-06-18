from __future__ import annotations

import sqlite3
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eqmarket.db import init_db
from eqmarket.log_importer import _load_known_item_index, insert_listing, split_listing_by_known_items
from eqmarket.log_parser import ParsedListing, normalize_item_name, parse_auction_line, parse_price_text, parse_sale_listings


@dataclass
class ListingPriceRepairStats:
    listings_seen: int = 0
    reparsed_prices: int = 0
    updated: int = 0


@dataclass
class ListingRawLineRepairStats:
    raw_lines_seen: int = 0
    raw_lines_reparsed: int = 0
    parse_skipped: int = 0
    listings_seen: int = 0
    listings_matched: int = 0
    listings_inserted: int = 0
    listings_discarded: int = 0


def repair_listing_prices(db_path: Path, *, server: str | None = None) -> ListingPriceRepairStats:
    """Repair stored listing price fields from price_raw without touching raw rows.

    This is intended for rows imported with older parser logic. For example,
    price_raw='2,000' should be stored as price_amount=2000 and price_pp=2000,
    not price_amount=2 and price_pp=2. Re-importing the same log will not fix
    those rows because market_listings.seen_hash makes imports idempotent.
    """
    init_db(db_path)
    stats = ListingPriceRepairStats()

    with closing(sqlite3.connect(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT listing_id, price_raw, price_amount, price_currency, price_pp
            FROM market_listings
            WHERE price_raw IS NOT NULL
              AND (? IS NULL OR lower(server) = lower(?))
            ORDER BY listing_id
            """,
            (server, server),
        ).fetchall()
        stats.listings_seen = len(rows)

        for row in rows:
            parsed = parse_price_text(str(row["price_raw"]))
            if parsed is None:
                continue

            _price_raw, price_amount, price_currency, price_pp = parsed
            if price_currency != "pp" or price_pp is None:
                continue

            stats.reparsed_prices += 1
            if (
                _optional_float(row["price_amount"]) == price_amount
                and _optional_text(row["price_currency"]) == price_currency
                and _optional_int(row["price_pp"]) == price_pp
            ):
                continue

            connection.execute(
                """
                UPDATE market_listings
                SET price_amount = ?,
                    price_currency = ?,
                    price_pp = ?
                WHERE listing_id = ?
                """,
                (price_amount, price_currency, price_pp, int(row["listing_id"])),
            )
            stats.updated += 1

        connection.commit()

    return stats


def repair_listing_raw_lines(
    db_path: Path,
    *,
    server: str | None = None,
    progress_callback: Any | None = None,
    progress_interval: int = 1000,
    commit_interval: int = 5000,
) -> ListingRawLineRepairStats:
    """Reparse stored EQ raw lines and discard listings the current parser rejects.

    Older parser versions could apply the next seen price to every comma-split
    item before that price. Re-importing the log inserts corrected rows but does
    not remove stale rows because market_listings is append-only/idempotent. This
    repair keeps raw rows for audit, inserts any newly expected parsed listings,
    and marks stale parser matches as discarded via market_listing_reviews.
    """
    init_db(db_path)
    stats = ListingRawLineRepairStats()

    with closing(sqlite3.connect(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        known_items = _load_known_item_index(connection)
        rows = connection.execute(
            """
            SELECT listing_id, server, raw_line, item_name, price_raw
            FROM market_listings
            WHERE source = 'eq_log'
              AND raw_line IS NOT NULL
              AND (? IS NULL OR lower(server) = lower(?))
            ORDER BY listing_id
            """,
            (server, server),
        ).fetchall()
        rows_by_raw_line: dict[tuple[str, str], list[sqlite3.Row]] = {}
        for row in rows:
            key = (str(row["server"]), str(row["raw_line"]))
            rows_by_raw_line.setdefault(key, []).append(row)

        stats.raw_lines_seen = len(rows_by_raw_line)

        for raw_line_index, ((db_server, raw_line), existing_rows) in enumerate(rows_by_raw_line.items(), start=1):
            auction = parse_auction_line(raw_line)
            if auction is None:
                stats.parse_skipped += 1
                _notify_progress(progress_callback, raw_line_index, stats.raw_lines_seen, stats, progress_interval)
                continue

            parsed_listings = parse_sale_listings(auction)
            if not parsed_listings:
                stats.parse_skipped += 1
                _notify_progress(progress_callback, raw_line_index, stats.raw_lines_seen, stats, progress_interval)
                continue

            expected_listings = [
                split_listing
                for listing in parsed_listings
                for split_listing in split_listing_by_known_items(listing, known_items)
            ]
            expected_by_signature: dict[tuple[str, str | None], list[ParsedListing]] = defaultdict(list)
            for listing in expected_listings:
                expected_by_signature[_parsed_listing_signature(listing)].append(listing)

            stats.raw_lines_reparsed += 1
            stats.listings_seen += len(existing_rows)

            mismatched_listing_ids: list[int] = []
            for row in existing_rows:
                signature = _row_listing_signature(row)
                if expected_by_signature.get(signature):
                    expected_by_signature[signature].pop()
                    stats.listings_matched += 1
                    continue
                mismatched_listing_ids.append(int(row["listing_id"]))

            for listing_id in mismatched_listing_ids:
                _discard_reparse_mismatch(connection, listing_id)
            stats.listings_discarded += len(mismatched_listing_ids)

            for remaining_listings in expected_by_signature.values():
                for listing in remaining_listings:
                    inserted, _pending = insert_listing(connection, db_server, listing)
                    if inserted:
                        stats.listings_inserted += 1

            _notify_progress(progress_callback, raw_line_index, stats.raw_lines_seen, stats, progress_interval)
            if commit_interval > 0 and raw_line_index % commit_interval == 0:
                connection.commit()

        connection.commit()
        _notify_progress(progress_callback, stats.raw_lines_seen, stats.raw_lines_seen, stats, 1)

    return stats


def _notify_progress(
    progress_callback: Any | None,
    current: int,
    total: int,
    stats: ListingRawLineRepairStats,
    progress_interval: int,
) -> None:
    if progress_callback is None or total <= 0:
        return
    if current != total and (progress_interval <= 0 or current % progress_interval != 0):
        return
    progress_callback(current, total, stats)


def _parsed_listing_signature(listing: ParsedListing) -> tuple[str, str | None]:
    return normalize_item_name(listing.item_name), _normalize_price_raw(listing.price_raw)


def _row_listing_signature(row: sqlite3.Row) -> tuple[str, str | None]:
    return normalize_item_name(str(row["item_name"])), _normalize_price_raw(row["price_raw"])


def _normalize_price_raw(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def _discard_reparse_mismatch(connection: sqlite3.Connection, listing_id: int) -> None:
    connection.execute(
        """
        INSERT INTO market_listing_reviews (listing_id, status, reason_code, note, updated_at)
        VALUES (?, 'discarded', 'parser_reparse_mismatch',
                'Current raw-line parser no longer emits this item/price pairing.', CURRENT_TIMESTAMP)
        ON CONFLICT(listing_id) DO UPDATE SET
            status = excluded.status,
            reason_code = excluded.reason_code,
            note = excluded.note,
            updated_at = CURRENT_TIMESTAMP
        """,
        (listing_id,),
    )


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None

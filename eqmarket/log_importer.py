from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from eqmarket.db import init_db
from eqmarket.log_parser import (
    ParsedListing,
    is_sale_message,
    iter_auction_messages,
    normalize_item_name,
    parse_auction_line,
    parse_sale_listings,
)


@dataclass
class LogImportStats:
    lines_read: int = 0
    auction_lines: int = 0
    sale_messages: int = 0
    listings_found: int = 0
    listings_inserted: int = 0
    pending_items_upserted: int = 0
    parse_issues_found: int = 0
    parse_issues_upserted: int = 0
    resumed_from_position: int = 0
    last_position: int = 0
    latest_sale_timestamp: str | None = None


KnownItemIndex = dict[tuple[str, ...], str]


def listing_seen_hash(server: str, listing: ParsedListing) -> str:
    payload = "\x1f".join(
        [
            server,
            listing.timestamp,
            listing.seller,
            normalize_item_name(listing.item_name),
            (listing.price_raw or "no_price").lower(),
            listing.raw_line,
        ]
    )
    return hashlib.sha1(payload.encode("utf-8", errors="replace")).hexdigest()


def _load_known_item_index(connection: sqlite3.Connection) -> KnownItemIndex:
    rows = connection.execute("SELECT normalized_name, name FROM items").fetchall()
    index: KnownItemIndex = {}
    for normalized_name, display_name in rows:
        tokens = tuple(str(normalized_name).split())
        if tokens:
            index[tokens] = str(display_name)
    return index


def split_listing_by_known_items(listing: ParsedListing, known_items: KnownItemIndex) -> list[ParsedListing]:
    """Split unseparated item runs using already-known DB item names.

    Example: "Deepwater Vambraces Crested Spaulders" can become two listings
    once both item names are present in items. We only split when the whole text
    can be covered by known item names, to avoid guessing through free text.
    """
    tokens = tuple(normalize_item_name(listing.item_name).split())
    if len(tokens) < 2 or tokens in known_items:
        return [listing]

    memo: dict[int, list[tuple[int, int]] | None] = {}

    def solve(start: int) -> list[tuple[int, int]] | None:
        if start == len(tokens):
            return []
        if start in memo:
            return memo[start]

        for end in range(len(tokens), start, -1):
            if tokens[start:end] not in known_items:
                continue
            rest = solve(end)
            if rest is not None:
                memo[start] = [(start, end), *rest]
                return memo[start]

        memo[start] = None
        return None

    spans = solve(0)
    if spans is None or len(spans) <= 1:
        return [listing]

    return [
        ParsedListing(
            timestamp=listing.timestamp,
            seller=listing.seller,
            item_name=known_items[tokens[start:end]],
            price_raw=listing.price_raw,
            price_amount=listing.price_amount,
            price_currency=listing.price_currency,
            price_pp=listing.price_pp,
            raw_line=listing.raw_line,
            confidence=f"{listing.confidence}_dict_split",
        )
        for start, end in spans
    ]


def _find_item_id(connection: sqlite3.Connection, normalized_name: str) -> int | None:
    row = connection.execute(
        "SELECT item_id FROM items WHERE normalized_name = ?",
        (normalized_name,),
    ).fetchone()
    return int(row[0]) if row else None


def insert_listing(connection: sqlite3.Connection, server: str, listing: ParsedListing) -> tuple[bool, bool]:
    """Insert one market listing. Returns (listing_inserted, pending_item_upserted)."""
    normalized_name = normalize_item_name(listing.item_name)
    item_id = _find_item_id(connection, normalized_name)
    seen_hash = listing_seen_hash(server, listing)

    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO market_listings (
            server, timestamp, seller,
            item_name, normalized_item_name, item_id,
            price_raw, price_amount, price_currency, price_pp,
            raw_line, source, confidence, seen_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'eq_log', ?, ?)
        """,
        (
            server,
            listing.timestamp,
            listing.seller,
            listing.item_name,
            normalized_name,
            item_id,
            listing.price_raw,
            listing.price_amount,
            listing.price_currency,
            listing.price_pp,
            listing.raw_line,
            listing.confidence,
            seen_hash,
        ),
    )
    listing_inserted = cursor.rowcount > 0

    pending_upserted = False
    if listing_inserted and item_id is None:
        connection.execute(
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
            (normalized_name, listing.item_name, listing.raw_line),
        )
        pending_upserted = True

    return listing_inserted, pending_upserted


def import_log_file(
    db_path: Path,
    log_path: Path,
    server: str,
    limit: int | None = None,
    incremental: bool = True,
    start_at_end_if_new: bool = False,
) -> LogImportStats:
    init_db(db_path)
    stats = LogImportStats()
    log_key = str(log_path.resolve())

    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        known_items = _load_known_item_index(connection)
        saved_position = _load_log_position(connection, log_key, server) if incremental else None
        file_size = log_path.stat().st_size
        if saved_position is None:
            start_position = file_size if incremental and start_at_end_if_new else 0
        else:
            start_position = saved_position
        if start_position > file_size:
            # Log was truncated/rotated/recreated.
            start_position = 0
        stats.resumed_from_position = start_position

        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(start_position)
            while line := handle.readline():
                stats.lines_read += 1
                auction = parse_auction_line(line)
                if auction is None:
                    if _looks_like_malformed_auction_line(line):
                        stats.parse_issues_found += 1
                        if _record_log_parse_issue(
                            connection,
                            server,
                            log_key,
                            raw_line=line.rstrip("\r\n"),
                            reason_code="malformed_auction_line",
                            reason="Line looked like /auction output but did not match the expected EQ log shape.",
                            timestamp_raw=_timestamp_raw_from_line(line),
                        ):
                            stats.parse_issues_upserted += 1
                    continue

                stats.auction_lines += 1
                parsed_listings = parse_sale_listings(auction)
                listings = [
                    split_listing
                    for listing in parsed_listings
                    for split_listing in split_listing_by_known_items(listing, known_items)
                ]
                if listings:
                    stats.sale_messages += 1
                elif is_sale_message(auction.message):
                    stats.parse_issues_found += 1
                    if _record_log_parse_issue(
                        connection,
                        server,
                        log_key,
                        raw_line=auction.raw_line,
                        reason_code="no_listing_candidates",
                        reason="Auction sale message did not contain a parseable item listing.",
                        timestamp=auction.timestamp,
                        timestamp_raw=auction.timestamp_raw,
                        seller=auction.seller,
                    ):
                        stats.parse_issues_upserted += 1
                stats.listings_found += len(listings)

                for listing in listings:
                    stats.latest_sale_timestamp = listing.timestamp
                    inserted, pending = insert_listing(connection, server, listing)
                    if inserted:
                        stats.listings_inserted += 1
                    if pending:
                        stats.pending_items_upserted += 1
                    if listing.price_raw is None:
                        stats.parse_issues_found += 1
                        if _record_log_parse_issue(
                            connection,
                            server,
                            log_key,
                            raw_line=listing.raw_line,
                            reason_code="no_price",
                            reason="Listing did not include a parseable platinum or Krono price.",
                            timestamp=listing.timestamp,
                            timestamp_raw=auction.timestamp_raw,
                            seller=listing.seller,
                        ):
                            stats.parse_issues_upserted += 1

                if limit is not None and stats.auction_lines >= limit:
                    break

            stats.last_position = handle.tell()

        if incremental:
            _save_log_position(connection, log_key, server, log_path, stats.last_position)
        connection.commit()

    return stats


def _record_log_parse_issue(
    connection: sqlite3.Connection,
    server: str,
    log_path: str,
    *,
    raw_line: str,
    reason_code: str,
    reason: str,
    timestamp: str | None = None,
    timestamp_raw: str | None = None,
    seller: str | None = None,
) -> bool:
    cursor = connection.execute(
        """
        INSERT INTO log_parse_issues (
            server, log_path, timestamp, timestamp_raw, seller, raw_line, reason_code, reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(server, log_path, raw_line, reason_code) DO UPDATE SET
            timestamp = COALESCE(excluded.timestamp, log_parse_issues.timestamp),
            timestamp_raw = COALESCE(excluded.timestamp_raw, log_parse_issues.timestamp_raw),
            seller = COALESCE(excluded.seller, log_parse_issues.seller),
            reason = excluded.reason,
            last_seen_at = CURRENT_TIMESTAMP,
            seen_count = seen_count + 1
        """,
        (server, log_path, timestamp, timestamp_raw, seller, raw_line, reason_code, reason),
    )
    return cursor.rowcount > 0


def _looks_like_malformed_auction_line(line: str) -> bool:
    lowered = line.lower()
    return " auctions," in lowered or "auction" in lowered and line.lstrip().startswith("[")


def _timestamp_raw_from_line(line: str) -> str | None:
    stripped = line.lstrip()
    if not stripped.startswith("["):
        return None
    end = stripped.find("]")
    if end <= 1:
        return None
    return stripped[1:end]


def _load_log_position(connection: sqlite3.Connection, log_path: str, server: str) -> int | None:
    row = connection.execute(
        """
        SELECT last_position
        FROM log_import_state
        WHERE log_path = ? AND lower(server) = lower(?)
        """,
        (log_path, server),
    ).fetchone()
    return int(row[0]) if row else None


def _save_log_position(
    connection: sqlite3.Connection,
    log_path: str,
    server: str,
    source_path: Path,
    last_position: int,
) -> None:
    stat = source_path.stat()
    connection.execute(
        """
        INSERT INTO log_import_state (
            log_path, server, file_size, file_mtime, last_position, updated_at
        ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(log_path, server) DO UPDATE SET
            file_size = excluded.file_size,
            file_mtime = excluded.file_mtime,
            last_position = excluded.last_position,
            updated_at = CURRENT_TIMESTAMP
        """,
        (log_path, server, stat.st_size, stat.st_mtime, last_position),
    )


def parse_log_file(log_path: Path, limit: int | None = None) -> list[ParsedListing]:
    """Parse a log without touching the database. Useful for dry-runs/previews."""
    listings: list[ParsedListing] = []
    for auction_index, auction in enumerate(iter_auction_messages(log_path), start=1):
        listings.extend(parse_sale_listings(auction))
        if limit is not None and auction_index >= limit:
            break
    return listings

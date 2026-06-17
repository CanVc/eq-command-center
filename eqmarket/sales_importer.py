from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from eqmarket.db import init_db
from eqmarket.log_parser import normalize_item_name
from eqmarket.sources.tlp_auctions import TlpAuctionsClient, TlpSale, db_server_name


TLP_SALES_SOURCE = "tlp_auctions_sales"
TLP_SALES_CURSOR_PREFIX = "tlp_sales_cursor"
TLP_SALES_PAGE_SIZE = 200


@dataclass(frozen=True)
class TlpSalesCursor:
    last_datetime: str
    last_id: int | None = None


@dataclass
class TlpSalesSyncStats:
    pages_fetched: int = 0
    sales_seen: int = 0
    sales_inserted: int = 0
    sales_updated: int = 0
    sales_skipped: int = 0
    items_upserted: int = 0
    krono_sales_converted: int = 0
    krono_price_pp: int | None = None
    previous_cursor_datetime: str | None = None
    previous_cursor_id: int | None = None
    next_cursor_datetime: str | None = None
    next_cursor_id: int | None = None


def sync_tlp_sales(
    db_path: Path,
    server: str,
    since_cursor: TlpSalesCursor | None = None,
    max_pages: int | None = None,
) -> TlpSalesSyncStats:
    """Synchronize recent WTS priced sales from TLP Auctions into market_listings."""
    init_db(db_path)
    db_server = db_server_name(server)
    api_server = db_server
    client = TlpAuctionsClient()
    stats = TlpSalesSyncStats()

    try:
        with closing(sqlite3.connect(db_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            cursor = since_cursor if since_cursor is not None else _load_sales_cursor(connection, db_server)
            _apply_previous_cursor(stats, cursor)
            stats.krono_price_pp = _load_latest_krono_price(connection, db_server)

            latest_cursor = cursor
            page = 1
            while max_pages is None or page <= max_pages:
                sales = client.get_sales(
                    api_server,
                    page=page,
                    page_size=TLP_SALES_PAGE_SIZE,
                    is_buy=False,
                    priced_only=True,
                )
                stats.pages_fetched += 1
                if not sales:
                    break

                page_has_cursor_overlap = False
                for sale in sales:
                    stats.sales_seen += 1
                    sale_datetime = _parse_sale_datetime(sale.datetime)
                    if sale_datetime is None or sale.is_buy or not _sale_has_price(sale):
                        stats.sales_skipped += 1
                        continue

                    if cursor is None or _sale_is_after_cursor(sale, cursor):
                        inserted, updated, item_upserted, krono_converted = _upsert_sale_listing(
                            connection,
                            db_server,
                            sale,
                            stats.krono_price_pp,
                        )
                        stats.sales_inserted += int(inserted)
                        stats.sales_updated += int(updated)
                        stats.items_upserted += int(item_upserted)
                        stats.krono_sales_converted += int(krono_converted)
                        latest_cursor = _max_cursor(latest_cursor, sale)

                    if cursor is None or _sale_is_cursor_overlap(sale, cursor):
                        page_has_cursor_overlap = True

                if cursor is not None and not page_has_cursor_overlap:
                    break
                page += 1

            if latest_cursor is not None:
                _save_sales_cursor(connection, db_server, latest_cursor)
                stats.next_cursor_datetime = latest_cursor.last_datetime
                stats.next_cursor_id = latest_cursor.last_id

            _record_sales_import_run(connection, db_server, stats, "completed", None)
            connection.commit()
    except Exception as exc:
        _record_failed_sales_import_run(db_path, db_server, stats, exc)
        raise

    return stats


def sales_stats_payload(stats: TlpSalesSyncStats | None) -> dict[str, object] | None:
    if stats is None:
        return None
    return asdict(stats)


def _apply_previous_cursor(stats: TlpSalesSyncStats, cursor: TlpSalesCursor | None) -> None:
    if cursor is None:
        return
    stats.previous_cursor_datetime = cursor.last_datetime
    stats.previous_cursor_id = cursor.last_id
    stats.next_cursor_datetime = cursor.last_datetime
    stats.next_cursor_id = cursor.last_id


def _load_sales_cursor(connection: sqlite3.Connection, db_server: str) -> TlpSalesCursor | None:
    row = connection.execute(
        "SELECT value FROM app_settings WHERE key = ?",
        (_cursor_key(db_server),),
    ).fetchone()
    if row is None:
        return None

    try:
        payload = json.loads(str(row[0]))
    except json.JSONDecodeError:
        return None

    last_datetime = payload.get("last_datetime")
    if not last_datetime:
        return None
    return TlpSalesCursor(last_datetime=str(last_datetime), last_id=_optional_int(payload.get("last_id")))


def _save_sales_cursor(connection: sqlite3.Connection, db_server: str, cursor: TlpSalesCursor) -> None:
    value = json.dumps(
        {"last_datetime": cursor.last_datetime, "last_id": cursor.last_id},
        ensure_ascii=False,
        sort_keys=True,
    )
    connection.execute(
        """
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
        """,
        (_cursor_key(db_server), value),
    )


def _cursor_key(db_server: str) -> str:
    return f"{TLP_SALES_CURSOR_PREFIX}:{db_server}"


def _load_latest_krono_price(connection: sqlite3.Connection, db_server: str) -> int | None:
    row = connection.execute(
        """
        SELECT price_pp
        FROM krono_prices
        WHERE lower(server) = ?
          AND price_pp IS NOT NULL
        ORDER BY datetime(last_refresh_at) DESC
        LIMIT 1
        """,
        (db_server,),
    ).fetchone()
    return int(row[0]) if row else None


def _sale_has_price(sale: TlpSale) -> bool:
    return sale.plat_price > 0 or sale.krono_price > 0


def _sale_is_after_cursor(sale: TlpSale, cursor: TlpSalesCursor) -> bool:
    sale_datetime = _parse_sale_datetime(sale.datetime)
    cursor_datetime = _parse_sale_datetime(cursor.last_datetime)
    if sale_datetime is None or cursor_datetime is None:
        return False
    if sale_datetime > cursor_datetime:
        return True
    if sale_datetime < cursor_datetime:
        return False
    if sale.sale_id is None or cursor.last_id is None:
        return sale.sale_id is None
    return sale.sale_id > cursor.last_id


def _sale_is_cursor_overlap(sale: TlpSale, cursor: TlpSalesCursor) -> bool:
    sale_datetime = _parse_sale_datetime(sale.datetime)
    cursor_datetime = _parse_sale_datetime(cursor.last_datetime)
    if sale_datetime is None or cursor_datetime is None:
        return False
    return sale_datetime >= cursor_datetime


def _max_cursor(cursor: TlpSalesCursor | None, sale: TlpSale) -> TlpSalesCursor:
    candidate = TlpSalesCursor(last_datetime=sale.datetime, last_id=sale.sale_id)
    if cursor is None:
        return candidate
    cursor_datetime = _parse_sale_datetime(cursor.last_datetime)
    candidate_datetime = _parse_sale_datetime(candidate.last_datetime)
    if cursor_datetime is None or candidate_datetime is None:
        return candidate
    if candidate_datetime > cursor_datetime:
        return candidate
    if candidate_datetime < cursor_datetime:
        return cursor
    if candidate.last_id is not None and (cursor.last_id is None or candidate.last_id > cursor.last_id):
        return candidate
    return cursor


def _upsert_sale_listing(
    connection: sqlite3.Connection,
    db_server: str,
    sale: TlpSale,
    krono_price_pp: int | None,
) -> tuple[bool, bool, bool, bool]:
    item_upserted = False
    normalized_name = normalize_item_name(sale.item_name)
    item_id = None
    if sale.item_id is not None:
        item_upserted = _upsert_minimal_item(connection, sale.item_id, sale.item_name)
        if _item_exists(connection, sale.item_id):
            item_id = sale.item_id

    price_raw, price_amount, price_currency, price_pp, krono_converted = _sale_price_fields(sale, krono_price_pp)
    seen_hash = _sale_seen_hash(db_server, sale)
    raw_line = _sale_raw_line(sale)
    existed = _listing_seen_hash_exists(connection, seen_hash)
    cursor = connection.execute(
        """
        INSERT INTO market_listings (
            server, timestamp, seller,
            item_name, normalized_item_name, item_id,
            price_raw, price_amount, price_currency, price_pp, krono_price_pp_used,
            raw_line, source, confidence, seen_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'tlp_sales', ?)
        ON CONFLICT(seen_hash) DO UPDATE SET
            timestamp = excluded.timestamp,
            seller = excluded.seller,
            item_name = excluded.item_name,
            normalized_item_name = excluded.normalized_item_name,
            item_id = COALESCE(excluded.item_id, market_listings.item_id),
            price_raw = excluded.price_raw,
            price_amount = excluded.price_amount,
            price_currency = excluded.price_currency,
            price_pp = excluded.price_pp,
            krono_price_pp_used = excluded.krono_price_pp_used,
            raw_line = excluded.raw_line,
            source = excluded.source,
            confidence = excluded.confidence,
            last_seen_at = CURRENT_TIMESTAMP,
            seen_count = market_listings.seen_count + 1
        """,
        (
            db_server,
            sale.datetime,
            sale.auctioneer,
            sale.item_name,
            normalized_name,
            item_id,
            price_raw,
            price_amount,
            price_currency,
            price_pp,
            krono_price_pp if krono_converted else None,
            raw_line,
            TLP_SALES_SOURCE,
            seen_hash,
        ),
    )
    inserted = cursor.rowcount > 0 and not existed
    updated = cursor.rowcount > 0 and existed
    return inserted, updated, item_upserted, krono_converted


def _upsert_minimal_item(connection: sqlite3.Connection, item_id: int, name: str) -> bool:
    normalized_name = normalize_item_name(name)
    try:
        cursor = connection.execute(
            """
            INSERT INTO items (
                item_id, name, normalized_name, source_primary, raw_payload,
                parser_version, last_imported_at, updated_at
            ) VALUES (?, ?, ?, 'tlp_auctions', ?, 'tlp_auctions_sales_v1', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(item_id) DO UPDATE SET
                source_primary = COALESCE(items.source_primary, excluded.source_primary),
                last_imported_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                item_id,
                name,
                normalized_name,
                json.dumps({"source": TLP_SALES_SOURCE}, ensure_ascii=False, sort_keys=True),
            ),
        )
    except sqlite3.IntegrityError:
        return False
    return cursor.rowcount > 0


def _item_exists(connection: sqlite3.Connection, item_id: int) -> bool:
    row = connection.execute("SELECT 1 FROM items WHERE item_id = ?", (item_id,)).fetchone()
    return row is not None


def _sale_price_fields(
    sale: TlpSale,
    krono_price_pp: int | None,
) -> tuple[str, float, str, int | None, bool]:
    plat_price = sale.plat_price if sale.plat_price > 0 else 0.0
    krono_price = sale.krono_price if sale.krono_price > 0 else 0.0
    krono_converted = krono_price > 0 and krono_price_pp is not None
    price_pp: int | None
    if krono_price > 0:
        price_pp = round(plat_price + krono_price * krono_price_pp) if krono_price_pp is not None else None
    else:
        price_pp = round(plat_price) if plat_price > 0 else None

    if krono_price > 0 and plat_price > 0:
        return f"{_format_number(krono_price)} krono + {_format_number(plat_price)}pp", krono_price, "mixed", price_pp, krono_converted
    if krono_price > 0:
        return f"{_format_number(krono_price)} krono", krono_price, "krono", price_pp, krono_converted
    return f"{_format_number(plat_price)}pp", plat_price, "pp", price_pp, False


def _format_number(value: float) -> str:
    if value == round(value):
        return str(round(value))
    return f"{value:g}"


def _sale_seen_hash(db_server: str, sale: TlpSale) -> str:
    if sale.sale_id is not None:
        return f"tlp_sale:{db_server}:{sale.sale_id}"
    if sale.raw_guid:
        return f"tlp_sale:{db_server}:raw_guid:{sale.raw_guid}"
    payload = "\x1f".join(
        [
            db_server,
            str(sale.item_id or ""),
            normalize_item_name(sale.item_name),
            sale.datetime,
            _format_number(sale.plat_price),
            _format_number(sale.krono_price),
            sale.auctioneer or "",
        ]
    )
    return f"tlp_sale:{db_server}:fallback:{payload}"


def _sale_raw_line(sale: TlpSale) -> str:
    payload = {
        "source": TLP_SALES_SOURCE,
        "id": sale.sale_id,
        "itemId": sale.item_id,
        "item": sale.item_name,
        "auctioneer": sale.auctioneer,
        "transactionType": sale.transaction_type,
        "platPrice": sale.plat_price,
        "kronoPrice": sale.krono_price,
        "datetime": sale.datetime,
        "rawGuid": sale.raw_guid,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _listing_seen_hash_exists(connection: sqlite3.Connection, seen_hash: str) -> bool:
    row = connection.execute("SELECT 1 FROM market_listings WHERE seen_hash = ?", (seen_hash,)).fetchone()
    return row is not None


def _record_sales_import_run(
    connection: sqlite3.Connection,
    db_server: str,
    stats: TlpSalesSyncStats,
    status: str,
    error: str | None,
) -> None:
    source_url = f"server={db_server};page_size={TLP_SALES_PAGE_SIZE};cursor={stats.previous_cursor_datetime or ''}"
    connection.execute(
        """
        INSERT INTO import_runs (
            source_name, source_url, status, items_seen, items_inserted,
            items_updated, error, finished_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            TLP_SALES_SOURCE,
            source_url,
            status,
            stats.sales_seen,
            stats.sales_inserted,
            stats.sales_updated,
            error,
        ),
    )


def _record_failed_sales_import_run(
    db_path: Path,
    db_server: str,
    stats: TlpSalesSyncStats,
    exc: Exception,
) -> None:
    try:
        with closing(sqlite3.connect(db_path)) as connection:
            _record_sales_import_run(connection, db_server, stats, "failed", str(exc)[:1000])
            connection.commit()
    except sqlite3.Error:
        return


def _parse_sale_datetime(value: str) -> datetime | None:
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _optional_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None

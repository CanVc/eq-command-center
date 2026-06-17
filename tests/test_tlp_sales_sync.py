from __future__ import annotations

from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eqmarket.db import init_db
from eqmarket.sales_importer import sync_tlp_sales
from eqmarket.sources.tlp_auctions import TlpSale


class TlpSalesSyncTests(unittest.TestCase):
    def test_sync_imports_sales_converts_krono_and_stores_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_krono_price(db_path, 17000)
            fake_client = _FakeSalesClient(
                {
                    1: [
                        _sale(3, "2026-06-17T10:05:00Z", "Krono Item", item_id=1003, plat=500, krono=1),
                        _sale(2, "2026-06-17T10:04:00Z", "Plat Item", item_id=1002, plat=1200),
                    ],
                    2: [],
                }
            )

            with patch("eqmarket.sales_importer.TlpAuctionsClient", return_value=fake_client):
                stats = sync_tlp_sales(db_path, "frostreaver")

            self.assertEqual(stats.pages_fetched, 2)
            self.assertEqual(stats.sales_seen, 2)
            self.assertEqual(stats.sales_inserted, 2)
            self.assertEqual(stats.krono_sales_converted, 1)
            self.assertEqual(stats.next_cursor_datetime, "2026-06-17T10:05:00Z")
            self.assertEqual(stats.next_cursor_id, 3)

            with closing(sqlite3.connect(db_path)) as connection:
                rows = connection.execute(
                    """
                    SELECT item_name, item_id, price_raw, price_amount, price_currency,
                           price_pp, krono_price_pp_used, source, seen_hash
                    FROM market_listings
                    ORDER BY timestamp DESC
                    """
                ).fetchall()
                cursor = _load_cursor(connection)
                import_run = connection.execute(
                    "SELECT status, items_seen, items_inserted FROM import_runs WHERE source_name = 'tlp_auctions_sales'"
                ).fetchone()

            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0][0], "Krono Item")
            self.assertEqual(rows[0][1], 1003)
            self.assertEqual(rows[0][2], "1 krono + 500pp")
            self.assertEqual(rows[0][3], 1)
            self.assertEqual(rows[0][4], "mixed")
            self.assertEqual(rows[0][5], 17500)
            self.assertEqual(rows[0][6], 17000)
            self.assertEqual(rows[0][7], "tlp_auctions_sales")
            self.assertEqual(rows[0][8], "tlp_sale:frostreaver:3")
            self.assertEqual(cursor, {"last_datetime": "2026-06-17T10:05:00Z", "last_id": 3})
            self.assertEqual(import_run, ("completed", 2, 2))
            self.assertEqual(fake_client.calls, [1, 2])

    def test_sync_stops_after_page_older_than_cursor_but_keeps_datetime_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_cursor(db_path, "2026-06-17T10:00:00Z", 10)
            fake_client = _FakeSalesClient(
                {
                    1: [
                        _sale(12, "2026-06-17T10:00:00Z", "Same Time Newer Id", item_id=1012, plat=500),
                        _sale(9, "2026-06-17T09:59:00Z", "Older Item", item_id=1009, plat=500),
                    ],
                    2: [_sale(8, "2026-06-17T09:58:00Z", "Old Page", item_id=1008, plat=500)],
                    3: [],
                }
            )

            with patch("eqmarket.sales_importer.TlpAuctionsClient", return_value=fake_client):
                stats = sync_tlp_sales(db_path, "frostreaver")

            self.assertEqual(stats.pages_fetched, 2)
            self.assertEqual(stats.sales_seen, 3)
            self.assertEqual(stats.sales_inserted, 1)
            self.assertEqual(stats.next_cursor_datetime, "2026-06-17T10:00:00Z")
            self.assertEqual(stats.next_cursor_id, 12)

            with closing(sqlite3.connect(db_path)) as connection:
                rows = connection.execute("SELECT item_name FROM market_listings").fetchall()
                cursor = _load_cursor(connection)

            self.assertEqual(rows, [("Same Time Newer Id",)])
            self.assertEqual(cursor, {"last_datetime": "2026-06-17T10:00:00Z", "last_id": 12})
            self.assertEqual(fake_client.calls, [1, 2])

    def test_sync_is_idempotent_when_run_twice(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            first_client = _FakeSalesClient(
                {1: [_sale(5, "2026-06-17T11:00:00Z", "Repeat Item", item_id=1005, plat=900)], 2: []}
            )
            second_client = _FakeSalesClient(
                {1: [_sale(5, "2026-06-17T11:00:00Z", "Repeat Item", item_id=1005, plat=900)], 2: []}
            )

            with patch("eqmarket.sales_importer.TlpAuctionsClient", return_value=first_client):
                first_stats = sync_tlp_sales(db_path, "frostreaver")
            with patch("eqmarket.sales_importer.TlpAuctionsClient", return_value=second_client):
                second_stats = sync_tlp_sales(db_path, "frostreaver")

            self.assertEqual(first_stats.sales_inserted, 1)
            self.assertEqual(second_stats.sales_inserted, 0)
            self.assertEqual(second_stats.sales_updated, 0)

            with closing(sqlite3.connect(db_path)) as connection:
                count = connection.execute("SELECT count(*) FROM market_listings").fetchone()[0]
                seen_count = connection.execute("SELECT seen_count FROM market_listings").fetchone()[0]

            self.assertEqual(count, 1)
            self.assertEqual(seen_count, 1)

    def test_sync_does_not_advance_cursor_or_commit_listings_after_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            fake_client = _FakeSalesClient(
                {
                    1: [_sale(7, "2026-06-17T12:00:00Z", "Interrupted Item", item_id=1007, plat=700)],
                    2: RuntimeError("network interrupted"),
                }
            )

            with patch("eqmarket.sales_importer.TlpAuctionsClient", return_value=fake_client):
                with self.assertRaises(RuntimeError):
                    sync_tlp_sales(db_path, "frostreaver")

            with closing(sqlite3.connect(db_path)) as connection:
                listing_count = connection.execute("SELECT count(*) FROM market_listings").fetchone()[0]
                cursor = _load_cursor(connection)
                import_run = connection.execute(
                    "SELECT status, items_seen, items_inserted, error FROM import_runs WHERE source_name = 'tlp_auctions_sales'"
                ).fetchone()

            self.assertEqual(listing_count, 0)
            self.assertIsNone(cursor)
            self.assertEqual(import_run[0], "failed")
            self.assertEqual(import_run[1], 1)
            self.assertEqual(import_run[2], 1)
            self.assertIn("network interrupted", import_run[3])


class _FakeSalesClient:
    def __init__(self, pages: dict[int, list[TlpSale] | Exception]) -> None:
        self.pages = pages
        self.calls: list[int] = []

    def get_sales(self, server_name: str, *, page: int, page_size: int, is_buy: bool, priced_only: bool) -> list[TlpSale]:
        self.calls.append(page)
        payload = self.pages.get(page, [])
        if isinstance(payload, Exception):
            raise payload
        return payload


def _sale(
    sale_id: int,
    timestamp: str,
    name: str,
    *,
    item_id: int,
    plat: float = 0,
    krono: float = 0,
) -> TlpSale:
    return TlpSale(
        sale_id=sale_id,
        item_id=item_id,
        item_name=name,
        auctioneer="Trader",
        transaction_type="WTS",
        plat_price=plat,
        krono_price=krono,
        datetime=timestamp,
        raw_guid=f"raw-{sale_id}",
        is_buy=False,
    )


def _seed_krono_price(db_path: Path, price_pp: int) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            """
            INSERT INTO krono_prices (server, price_pp, source, confidence, last_refresh_at)
            VALUES ('frostreaver', ?, 'fixture', 'high', '2026-06-17T09:00:00Z')
            """,
            (price_pp,),
        )
        connection.commit()


def _seed_cursor(db_path: Path, last_datetime: str, last_id: int) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            """
            INSERT INTO app_settings (key, value)
            VALUES ('tlp_sales_cursor:frostreaver', ?)
            """,
            (json.dumps({"last_datetime": last_datetime, "last_id": last_id}),),
        )
        connection.commit()


def _load_cursor(connection: sqlite3.Connection) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT value FROM app_settings WHERE key = 'tlp_sales_cursor:frostreaver'"
    ).fetchone()
    return json.loads(row[0]) if row else None


if __name__ == "__main__":
    unittest.main()

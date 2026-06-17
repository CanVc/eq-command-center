from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from threading import Lock
from unittest.mock import patch

from fastapi.testclient import TestClient

from eqmarket.api.app import create_app
from eqmarket.db import init_db
from eqmarket.price_importer import TlpPriceImportStats, import_tlp_prices
from eqmarket.sources.tlp_auctions import CatalogItem, KronoPrice, PricePoint, TlpAuctionsClient


class TlpAuctionsClientTests(unittest.TestCase):
    def test_krono_price_prefers_one_day_window_used_by_tlp_ui(self) -> None:
        class FakeClient(TlpAuctionsClient):
            def _get_json(self, path: str, params: dict[str, object] | None = None) -> dict[str, object]:
                if path == "/api/krono-prices/Frostreaver/windows":
                    return {
                        "serverName": "Frostreaver",
                        "windows": [
                            {"days": 1, "averagePrice": 17463.052, "sampleSize": 249},
                            {"days": 7, "averagePrice": 14427.882, "sampleSize": 1357},
                        ],
                        "lastUpdated": "2026-06-17T17:59:45Z",
                    }
                raise AssertionError(f"unexpected path: {path}")

        price = FakeClient().get_krono_price("frostreaver")

        if price is None:
            self.fail("expected a Krono price")
        self.assertEqual(price.average_price, 17463.052)
        self.assertEqual(price.sample_size, 249)
        self.assertEqual(price.last_updated, "2026-06-17T17:59:45Z")


class ApiPriceRefreshTests(unittest.TestCase):
    def test_krono_refresh_updates_cache_and_converts_krono_listings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_krono_listing(db_path)
            app = create_app(db_path)

            with patch("eqmarket.price_importer.TlpAuctionsClient") as client_class:
                client_class.return_value.get_krono_price.return_value = KronoPrice(
                    server_name="Frostreaver",
                    average_price=17463.052,
                    sample_size=249,
                    last_updated="2026-06-17T17:59:45Z",
                )
                with TestClient(app) as client:
                    response = client.post("/api/krono/refresh", params={"server": "frostreaver"})

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.json(),
                {
                    "server": "frostreaver",
                    "krono_updated": True,
                    "krono_price_pp": 17463,
                    "krono_listings_converted": 1,
                },
            )

            with closing(sqlite3.connect(db_path)) as connection:
                krono = connection.execute(
                    "SELECT price_pp, source, confidence, last_refresh_at FROM krono_prices WHERE server = 'frostreaver'"
                ).fetchone()
                listing = connection.execute(
                    "SELECT price_pp, krono_price_pp_used FROM market_listings WHERE listing_id = 1"
                ).fetchone()

            self.assertEqual(krono, (17463, "tlp_auctions", "high", "2026-06-17T17:59:45Z"))
            self.assertEqual(listing, (34926, 17463))

    def test_global_tlp_refresh_targets_missing_or_stale_recent_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_stale_price_fixture(db_path)
            app = create_app(db_path)
            stats = TlpPriceImportStats(
                catalog_items_seen=10,
                history_items_checked=2,
                history_prices_upserted=2,
                krono_updated=True,
                krono_price_pp=17463,
            )

            with patch("eqmarket.api.routes.prices.import_tlp_prices", return_value=stats) as importer:
                with TestClient(app) as client:
                    response = client.post(
                        "/api/tlp-prices/refresh",
                        params={"server": "frostreaver", "max_age_hours": 6, "limit": 10},
                    )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["server"], "frostreaver")
            self.assertEqual(payload["target_count"], 2)
            self.assertEqual(set(payload["target_item_ids"]), {101, 103})
            self.assertEqual(payload["history_prices_upserted"], 2)

            importer.assert_called_once()
            self.assertEqual(importer.call_args.kwargs["item_ids"], payload["target_item_ids"])
            self.assertEqual(importer.call_args.kwargs["history_days"], 3)
            self.assertEqual(importer.call_args.kwargs["concurrency"], 5)
            self.assertEqual(payload["concurrency"], 5)

    def test_tlp_refresh_job_reports_progress_until_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_stale_price_fixture(db_path)
            app = create_app(db_path)
            stats = TlpPriceImportStats(
                catalog_items_seen=10,
                history_items_checked=2,
                history_prices_upserted=2,
                krono_updated=True,
                krono_price_pp=17463,
            )

            def fake_import(*args, **kwargs):
                progress_callback = kwargs.get("progress_callback")
                if progress_callback is not None:
                    progress_callback({"phase": "history", "completed": 1, "total": 2, "item_id": 101})
                    progress_callback({"phase": "history", "completed": 2, "total": 2, "item_id": 103})
                return stats

            with patch("eqmarket.api.routes.prices.import_tlp_prices", side_effect=fake_import):
                with TestClient(app) as client:
                    response = client.post(
                        "/api/tlp-prices/refresh-jobs",
                        params={"server": "frostreaver", "max_age_hours": 6, "limit": 10},
                    )
                    self.assertEqual(response.status_code, 200)
                    job_id = response.json()["job_id"]

                    status_payload = _poll_job_until_finished(client, job_id)

            self.assertEqual(status_payload["status"], "completed")
            self.assertEqual(status_payload["phase"], "completed")
            self.assertEqual(status_payload["completed"], 2)
            self.assertEqual(status_payload["total"], 2)
            self.assertEqual(set(status_payload["target_item_ids"]), {101, 103})
            self.assertEqual(status_payload["stats"]["history_prices_upserted"], 2)
            self.assertEqual(status_payload["concurrency"], 5)
            self.assertEqual(status_payload["stats"]["concurrency"], 5)


class PriceImporterConcurrencyTests(unittest.TestCase):
    def test_import_tlp_prices_fetches_item_histories_in_parallel(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_parallel_item_fixture(db_path)
            fake_client = _ConcurrentFakeTlpClient()

            with patch("eqmarket.price_importer.TlpAuctionsClient", return_value=fake_client):
                stats = import_tlp_prices(
                    db_path,
                    "frostreaver",
                    item_ids=[201, 202, 203, 204],
                    history_days=None,
                    concurrency=4,
                )

            self.assertEqual(stats.history_items_checked, 4)
            self.assertEqual(stats.history_prices_upserted, 4)
            self.assertGreater(fake_client.max_active, 1)


class _ConcurrentFakeTlpClient:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self._lock = Lock()

    def get_krono_price(self, server_name: str) -> KronoPrice:
        return KronoPrice(
            server_name="Frostreaver",
            average_price=17463,
            sample_size=50,
            last_updated="2026-06-17T17:59:45Z",
        )

    def get_catalog(self, server_name: str) -> list[CatalogItem]:
        return [CatalogItem(item_id=item_id, name=f"Parallel Item {item_id}", price=1000) for item_id in range(201, 205)]

    def get_item_history(self, item_id: int, server_name: str) -> list[PricePoint]:
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)

        time.sleep(0.05)

        with self._lock:
            self.active -= 1

        return [
            PricePoint(
                datetime="2026-06-17T10:00:00Z",
                plat_price=1000 + item_id,
                krono_price=0,
                is_buy=False,
                auctioneer="Fixture",
            )
        ]


def _poll_job_until_finished(client: TestClient, job_id: str) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(f"/api/tlp-prices/refresh-jobs/{job_id}")
        if response.status_code != 200:
            raise AssertionError(response.text)
        payload = response.json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError("TLP refresh job did not finish")


def _seed_krono_listing(db_path: Path) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            INSERT INTO market_listings (
                listing_id, server, timestamp, seller, item_name, normalized_item_name,
                price_raw, price_amount, price_currency, price_pp, source, confidence
            ) VALUES (1, 'frostreaver', CURRENT_TIMESTAMP, 'KronoSeller', 'Any Item', 'any item',
                      '2 krono', 2, 'krono', NULL, 'eq_log', 'parsed')
            """
        )
        connection.commit()


def _seed_parallel_item_fixture(db_path: Path) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executemany(
            "INSERT INTO items (item_id, name, normalized_name) VALUES (?, ?, ?)",
            [(item_id, f"Parallel Item {item_id}", f"parallel item {item_id}") for item_id in range(201, 205)],
        )
        connection.commit()


def _seed_stale_price_fixture(db_path: Path) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executemany(
            "INSERT INTO items (item_id, name, normalized_name) VALUES (?, ?, ?)",
            [
                (101, "Stale Item", "stale item"),
                (102, "Fresh Item", "fresh item"),
                (103, "Missing Price Item", "missing price item"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO market_prices (
                item_id, server, median_pp, sample_size, confidence, last_refresh_at, source
            ) VALUES (?, 'frostreaver', ?, 5, 'medium', datetime('now', ?), 'fixture')
            """,
            [
                (101, 10000, "-7 hours"),
                (102, 20000, "-1 hour"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO market_listings (
                server, timestamp, seller, item_name, normalized_item_name, item_id,
                price_raw, price_pp, source, confidence
            ) VALUES ('frostreaver', datetime('now', ?), ?, ?, ?, ?, '1k', 1000, 'eq_log', 'parsed')
            """,
            [
                ("-1 hour", "StaleSeller", "Stale Item", "stale item", 101),
                ("-2 hours", "FreshSeller", "Fresh Item", "fresh item", 102),
                ("-30 minutes", "MissingSeller", "Missing Price Item", "missing price item", 103),
            ],
        )
        connection.commit()


if __name__ == "__main__":
    unittest.main()

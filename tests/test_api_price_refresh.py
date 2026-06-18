from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event, Lock
from unittest.mock import patch

from fastapi.testclient import TestClient

from eqmarket.api.app import create_app
from eqmarket.db import init_db
from eqmarket.price_importer import TlpPriceImportStats, import_tlp_prices, load_recent_listing_item_ids
from eqmarket.sources.tlp_auctions import CatalogItem, KronoPrice, PricePoint, TlpAuctionsClient, TlpAuctionsError


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
            self.assertEqual(importer.call_args.kwargs["concurrency"], 10)
            self.assertEqual(payload["concurrency"], 10)

    def test_runtime_status_reports_stale_items_and_latest_log_sale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_stale_price_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get(
                    "/api/runtime/status",
                    params={"server": "frostreaver", "max_age_hours": 6},
                )

            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertEqual(payload["server"], "frostreaver")
            self.assertEqual(payload["stale_item_count"], 2)
            self.assertIsNotNone(payload["latest_log_sale_at"])
            self.assertIsNotNone(payload["log_watcher"])

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
            self.assertEqual(status_payload["concurrency"], 10)
            self.assertEqual(status_payload["stats"]["concurrency"], 10)

    def test_tlp_refresh_job_reuses_active_job_instead_of_queueing_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_stale_price_fixture(db_path)
            app = create_app(db_path)
            started = Event()
            release = Event()

            def blocking_import(*args, **kwargs):
                started.set()
                release.wait(timeout=5)
                return TlpPriceImportStats(history_items_checked=2, history_prices_upserted=2)

            with patch("eqmarket.api.routes.prices.import_tlp_prices", side_effect=blocking_import) as importer:
                with TestClient(app) as client:
                    first_response = client.post(
                        "/api/tlp-prices/refresh-jobs",
                        params={"server": "frostreaver", "max_age_hours": 6, "limit": 10},
                    )
                    self.assertEqual(first_response.status_code, 200)
                    self.assertTrue(started.wait(timeout=2))

                    second_response = client.post(
                        "/api/tlp-prices/refresh-jobs",
                        params={"server": "frostreaver", "max_age_hours": 6, "limit": 10},
                    )
                    release.set()
                    status_payload = _poll_job_until_finished(client, first_response.json()["job_id"])

            self.assertEqual(second_response.status_code, 200)
            self.assertEqual(second_response.json()["job_id"], first_response.json()["job_id"])
            self.assertEqual(status_payload["status"], "completed")
            self.assertEqual(importer.call_count, 1)

    def test_tlp_refresh_job_can_skip_krono_when_no_items_are_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            app = create_app(db_path)

            with (
                patch("eqmarket.api.routes.prices.import_tlp_prices") as importer,
                patch("eqmarket.api.routes.prices.refresh_krono_price") as krono_refresh,
            ):
                with TestClient(app) as client:
                    response = client.post(
                        "/api/tlp-prices/refresh-jobs",
                        params={
                            "server": "frostreaver",
                            "refresh_krono_when_empty": False,
                        },
                    )
                    self.assertEqual(response.status_code, 200)
                    status_payload = _poll_job_until_finished(client, response.json()["job_id"])

            self.assertEqual(status_payload["status"], "completed")
            self.assertEqual(status_payload["target_count"], 0)
            self.assertEqual(status_payload["stats"]["target_count"], 0)
            self.assertFalse(status_payload["stats"]["krono_updated"])
            importer.assert_not_called()
            krono_refresh.assert_not_called()


class PriceImporterConcurrencyTests(unittest.TestCase):
    def test_import_tlp_prices_links_duplicate_catalog_name_to_existing_canonical_item(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_duplicate_catalog_name_fixture(db_path)

            with patch("eqmarket.price_importer.TlpAuctionsClient", return_value=_DuplicateCatalogFakeTlpClient()):
                stats = import_tlp_prices(db_path, "frostreaver", fetch_history=False)

            self.assertEqual(stats.listings_linked, 1)
            with closing(sqlite3.connect(db_path)) as connection:
                listing_item_id = connection.execute("SELECT item_id FROM market_listings").fetchone()[0]
                violations = connection.execute("PRAGMA foreign_key_check").fetchall()

            self.assertEqual(listing_item_id, 1)
            self.assertEqual(violations, [])

    def test_failed_price_marker_counts_as_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_failed_refresh_item_fixture(db_path, item_id=302, with_failed_marker=True)

            self.assertIn(
                302,
                load_recent_listing_item_ids(db_path, "frostreaver", 10, max_age_hours=6),
            )

    def test_failed_item_history_refresh_remains_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_failed_refresh_item_fixture(db_path)

            with patch("eqmarket.price_importer.TlpAuctionsClient", return_value=_FailingHistoryFakeTlpClient()):
                stats = import_tlp_prices(
                    db_path,
                    "frostreaver",
                    item_ids=[301],
                    history_days=None,
                    concurrency=1,
                )

            self.assertEqual(stats.price_refresh_failed, 1)
            self.assertIn(
                301,
                load_recent_listing_item_ids(db_path, "frostreaver", 10, max_age_hours=6),
            )
            with closing(sqlite3.connect(db_path)) as connection:
                market_price = connection.execute(
                    "SELECT 1 FROM market_prices WHERE item_id = 301 AND server = 'frostreaver'"
                ).fetchone()

            self.assertIsNone(market_price)

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


class _DuplicateCatalogFakeTlpClient:
    def get_krono_price(self, server_name: str) -> None:
        return None

    def get_catalog(self, server_name: str) -> list[CatalogItem]:
        return [CatalogItem(item_id=2, name="Duplicate Item", price=1000)]


class _FailingHistoryFakeTlpClient:
    def get_krono_price(self, server_name: str) -> None:
        return None

    def get_catalog(self, server_name: str) -> list[CatalogItem]:
        return [CatalogItem(item_id=301, name="Failed Refresh Item", price=1000)]

    def get_item_history(self, item_id: int, server_name: str) -> list[PricePoint]:
        raise TlpAuctionsError("temporary upstream error")


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


def _seed_duplicate_catalog_name_fixture(db_path: Path) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "INSERT INTO items (item_id, name, normalized_name) VALUES (1, 'Duplicate Item', 'duplicate item')"
        )
        connection.execute(
            """
            INSERT INTO market_listings (
                server, timestamp, seller, item_name, normalized_item_name,
                price_raw, price_pp, source, confidence
            ) VALUES ('frostreaver', CURRENT_TIMESTAMP, 'Seller', 'Duplicate Item',
                      'duplicate item', '1k', 1000, 'eq_log', 'parsed')
            """
        )
        connection.commit()


def _seed_failed_refresh_item_fixture(
    db_path: Path,
    *,
    item_id: int = 301,
    with_failed_marker: bool = False,
) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "INSERT INTO items (item_id, name, normalized_name) VALUES (?, 'Failed Refresh Item', 'failed refresh item')",
            (item_id,),
        )
        connection.execute(
            """
            INSERT INTO market_listings (
                server, timestamp, seller, item_name, normalized_item_name, item_id,
                price_raw, price_pp, source, confidence
            ) VALUES ('frostreaver', CURRENT_TIMESTAMP, 'Seller', 'Failed Refresh Item',
                      'failed refresh item', ?, '1k', 1000, 'eq_log', 'parsed')
            """,
            (item_id,),
        )
        if with_failed_marker:
            connection.execute(
                """
                INSERT INTO market_prices (
                    item_id, server, sample_size, confidence, last_refresh_at, source
                ) VALUES (?, 'frostreaver', 0, 'failed', CURRENT_TIMESTAMP, 'tlp_auctions_history_failed')
                """,
                (item_id,),
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

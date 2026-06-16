from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from eqmarket.api.app import create_app
from eqmarket.db import init_db


class ApiDashboardTests(unittest.TestCase):
    def test_summary_aggregates_recent_server_metrics_and_price_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_dashboard_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/dashboard/summary", params={"server": "Frostreaver"})

            self.assertEqual(response.status_code, 200)
            payload = response.json()

            self.assertEqual(payload["server"], "frostreaver")
            self.assertEqual(payload["listings_recent_count"], 3)
            self.assertEqual(payload["deals_recent_count"], 2)
            self.assertEqual(payload["krono_latest"]["price_pp"], 16000)

            self.assertEqual(payload["top_seen_items"][0]["item_id"], 101)
            self.assertEqual(payload["top_seen_items"][0]["item_name"], "Stave of Shielding")
            self.assertEqual(payload["top_seen_items"][0]["seen_count"], 2)

            self.assertEqual([deal["item_id"] for deal in payload["top_discounts"]], [101, 102])
            self.assertEqual(payload["top_discounts"][0]["market_price_pp"], 10000)
            self.assertEqual(payload["top_discounts"][0]["market_price_source"], "avg_pp")
            self.assertEqual(payload["top_discounts"][0]["discount_pct"], 60.0)

    def test_krono_latest_returns_empty_payload_when_server_has_no_krono_price(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/krono/latest", params={"server": "frostreaver"})
                summary_response = client.get("/api/dashboard/summary", params={"server": "frostreaver"})

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.json(),
                {
                    "server": "frostreaver",
                    "price_pp": None,
                    "source": None,
                    "confidence": None,
                    "last_refresh_at": None,
                },
            )
            self.assertEqual(summary_response.status_code, 200)
            self.assertIsNone(summary_response.json()["krono_latest"]["price_pp"])


def _seed_dashboard_fixture(db_path: Path) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executemany(
            """
            INSERT INTO items (item_id, name, normalized_name)
            VALUES (?, ?, ?)
            """,
            [
                (101, "Stave of Shielding", "stave of shielding"),
                (102, "Cloak of Flames", "cloak of flames"),
                (103, "Other Server Item", "other server item"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO market_prices (
                item_id, server, median_pp, p25_pp, avg_pp, sample_size, confidence, last_refresh_at, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            """,
            [
                (101, "frostreaver", 0, 8000, 10000, 3, "low", "fixture"),
                (102, "frostreaver", 100000, 90000, 110000, 20, "high", "fixture"),
                (103, "other", 20000, 18000, 22000, 5, "medium", "fixture"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO market_listings (
                server, timestamp, seller, item_name, normalized_item_name, item_id,
                price_raw, price_pp, source, confidence
            ) VALUES (?, datetime('now', ?), ?, ?, ?, ?, ?, ?, 'eq_log', 'parsed')
            """,
            [
                ("frostreaver", "-1 hour", "Nebblastin", "Stave of Shielding", "stave of shielding", 101, "4k", 4000),
                ("frostreaver", "-2 hours", "SellerTwo", "Stave of Shielding", "stave of shielding", 101, "9k", 9000),
                ("frostreaver", "-3 hours", "SellerThree", "Cloak of Flames", "cloak of flames", 102, "70k", 70000),
                ("frostreaver", "-2 days", "OldSeller", "Cloak of Flames", "cloak of flames", 102, "1k", 1000),
                ("other", "-1 hour", "OtherSeller", "Other Server Item", "other server item", 103, "1k", 1000),
            ],
        )
        connection.execute(
            """
            INSERT INTO krono_prices (server, price_pp, source, confidence, last_refresh_at)
            VALUES ('frostreaver', 16000, 'fixture', 'high', CURRENT_TIMESTAMP)
            """
        )
        connection.commit()

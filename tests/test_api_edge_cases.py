from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from eqmarket.api.app import create_app
from eqmarket.db import init_db


class ApiEdgeCaseTests(unittest.TestCase):
    def test_endpoint_returns_503_when_database_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "missing.sqlite"
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/listings/recent")

            self.assertEqual(response.status_code, 503)
            self.assertIn("SQLite database is not readable", response.json()["detail"])

    def test_blank_server_is_rejected_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/deals", params={"server": "   "})

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), {"detail": "server must not be blank"})

    def test_listing_search_treats_like_wildcards_as_literal_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_literal_search_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                percent_response = client.get("/api/listings/recent", params={"server": "frostreaver", "q": "%"})
                underscore_response = client.get("/api/listings/recent", params={"server": "frostreaver", "q": "_"})

            self.assertEqual(percent_response.status_code, 200)
            self.assertEqual([listing["item_name"] for listing in percent_response.json()], ["Trader 100% Sword"])

            self.assertEqual(underscore_response.status_code, 200)
            self.assertEqual([listing["item_name"] for listing in underscore_response.json()], ["Trader_Only Shield"])


def _seed_literal_search_fixture(db_path: Path) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executemany(
            """
            INSERT INTO market_listings (
                server, timestamp, seller, item_name, normalized_item_name,
                price_raw, price_pp, source, confidence
            ) VALUES ('frostreaver', ?, ?, ?, ?, '1k', 1000, 'eq_log', 'parsed')
            """,
            [
                ("2026-06-16 10:00:00", "PercentSeller", "Trader 100% Sword", "trader 100% sword"),
                ("2026-06-16 11:00:00", "UnderscoreSeller", "Trader_Only Shield", "trader_only shield"),
                ("2026-06-16 12:00:00", "NormalSeller", "Normal Sword", "normal sword"),
            ],
        )
        connection.commit()


if __name__ == "__main__":
    unittest.main()

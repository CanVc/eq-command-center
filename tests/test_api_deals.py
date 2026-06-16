from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from eqmarket.api.app import create_app
from eqmarket.db import init_db


class ApiDealsTests(unittest.TestCase):
    def test_deals_are_sorted_and_include_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            listing_ids = _seed_deals_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/deals", params={"server": "Frostreaver", "min_discount": 30})

            self.assertEqual(response.status_code, 200)
            payload = response.json()

            self.assertEqual(
                [deal["listing_id"] for deal in payload],
                [listing_ids["larger_gain"], listing_ids["median"], listing_ids["p25_fallback"], listing_ids["avg_fallback"]],
            )
            self.assertEqual(payload[0]["item"], {"item_id": 106, "name": "Runed Crown"})
            self.assertEqual(payload[0]["seller"], "BigSeller")
            self.assertEqual(payload[0]["price_raw"], "8k")
            self.assertEqual(payload[0]["listing_price_pp"], 8000)
            self.assertEqual(payload[0]["market_price_pp"], 20000)
            self.assertEqual(payload[0]["market_price_source"], "median_pp")
            self.assertEqual(payload[0]["discount_pct"], 60.0)
            self.assertEqual(payload[0]["potential_profit_pp"], 12000)
            self.assertEqual(payload[0]["score"], 88.5)
            self.assertEqual(payload[0]["deal_score"], 88.5)
            self.assertTrue(payload[0]["resolved"])

            self.assertEqual(payload[2]["market_price_pp"], 7000)
            self.assertEqual(payload[2]["market_price_source"], "p25_pp")
            self.assertEqual(payload[2]["discount_pct"], 42.86)

            self.assertEqual(payload[3]["market_price_pp"], 10000)
            self.assertEqual(payload[3]["market_price_source"], "avg_pp")
            self.assertEqual(payload[3]["discount_pct"], 35.0)

    def test_min_discount_min_price_and_limit_filter_deals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            listing_ids = _seed_deals_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get(
                    "/api/deals",
                    params={
                        "server": "frostreaver",
                        "min_discount": 50,
                        "min_price_pp": 5000,
                        "limit": 1,
                    },
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()

            self.assertEqual([deal["listing_id"] for deal in payload], [listing_ids["larger_gain"]])

    def test_deals_exclude_zero_or_missing_listing_and_market_prices(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            listing_ids = _seed_deals_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/deals", params={"server": "frostreaver", "resolved_only": "false"})

            self.assertEqual(response.status_code, 200)
            listing_ids_seen = {deal["listing_id"] for deal in response.json()}

            self.assertNotIn(listing_ids["zero_listing_price"], listing_ids_seen)
            self.assertNotIn(listing_ids["missing_market_price"], listing_ids_seen)
            self.assertNotIn(listing_ids["unresolved"], listing_ids_seen)


def _seed_deals_fixture(db_path: Path) -> dict[str, int]:
    listing_ids: dict[str, int] = {}

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
                (103, "Fungi Covered Scale Tunic", "fungi covered scale tunic"),
                (104, "Null Market Item", "null market item"),
                (105, "Zero Listing Item", "zero listing item"),
                (106, "Runed Crown", "runed crown"),
                (107, "P25 Fallback Item", "p25 fallback item"),
                (108, "Other Server Item", "other server item"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO market_prices (
                item_id, server, median_pp, p25_pp, avg_pp, sample_size, confidence, last_refresh_at, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 'fixture')
            """,
            [
                (101, "frostreaver", 10000, 8000, 11000, 12, "high"),
                (102, "frostreaver", 0, 8000, 10000, 3, "low"),
                (103, "frostreaver", 20000, 15000, 21000, 9, "medium"),
                (104, "frostreaver", None, None, None, 0, "none"),
                (105, "frostreaver", 5000, 4000, 5500, 5, "medium"),
                (106, "frostreaver", 20000, 15000, 21000, 8, "medium"),
                (107, "frostreaver", 0, 7000, 0, 2, "low"),
                (108, "other", 10000, 8000, 11000, 5, "high"),
            ],
        )

        listing_rows = [
            ("median", "frostreaver", "-1 hour", "Nebblastin", "Stave of Shielding", "stave of shielding", 101, "4k", 4000),
            ("avg_fallback", "frostreaver", "-2 hours", "SellerTwo", "Cloak of Flames", "cloak of flames", 102, "6500", 6500),
            ("below_discount", "frostreaver", "-3 hours", "SellerThree", "Fungi Covered Scale Tunic", "fungi covered scale tunic", 103, "15k", 15000),
            ("missing_market_price", "frostreaver", "-4 hours", "SellerFour", "Null Market Item", "null market item", 104, "1k", 1000),
            ("zero_listing_price", "frostreaver", "-5 hours", "SellerFive", "Zero Listing Item", "zero listing item", 105, "free", 0),
            ("larger_gain", "frostreaver", "-6 hours", "BigSeller", "Runed Crown", "runed crown", 106, "8k", 8000),
            ("p25_fallback", "frostreaver", "-7 hours", "SellerSeven", "P25 Fallback Item", "p25 fallback item", 107, "4k", 4000),
            ("other_server", "other", "-1 hour", "OtherSeller", "Other Server Item", "other server item", 108, "1k", 1000),
            ("unresolved", "frostreaver", "-1 hour", "MysterySeller", "Mystery Item", "mystery item", None, "1k", 1000),
        ]

        for key, server, timestamp_modifier, seller, item_name, normalized_name, item_id, price_raw, price_pp in listing_rows:
            cursor = connection.execute(
                """
                INSERT INTO market_listings (
                    server, timestamp, seller, item_name, normalized_item_name, item_id,
                    price_raw, price_pp, source, confidence
                ) VALUES (?, datetime('now', ?), ?, ?, ?, ?, ?, ?, 'eq_log', 'parsed')
                """,
                (server, timestamp_modifier, seller, item_name, normalized_name, item_id, price_raw, price_pp),
            )
            listing_ids[key] = int(cursor.lastrowid)

        connection.execute(
            """
            INSERT INTO scoring_profiles (profile_name, profile_type, config_json, enabled)
            VALUES ('market_deals', 'market_deals', '{}', 1)
            """
        )
        connection.execute(
            """
            INSERT INTO listing_scores (listing_id, profile_name, deal_score, alert_level, reason)
            VALUES (?, 'market_deals', 88.5, 'critical', 'fixture score')
            """,
            (listing_ids["larger_gain"],),
        )
        connection.commit()

    return listing_ids

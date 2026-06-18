from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime, timedelta
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
            self.assertEqual(
                payload[0]["raw_line"],
                "[Tue Jun 16 10:00:00 2026] BigSeller auctions, 'WTS Runed Crown 8k'",
            )
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

    def test_seller_item_and_date_from_filter_deals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            listing_ids = _seed_deals_fixture(db_path)
            _move_listing_timestamp(db_path, listing_ids["larger_gain"], "-2 days")
            app = create_app(db_path)
            date_from = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()

            with TestClient(app) as client:
                seller_response = client.get("/api/deals", params={"server": "frostreaver", "seller": " big "})
                item_response = client.get("/api/deals", params={"server": "frostreaver", "item": "crown"})
                date_response = client.get(
                    "/api/deals",
                    params={"server": "frostreaver", "min_discount": 30, "date_from": date_from},
                )

            self.assertEqual(seller_response.status_code, 200, seller_response.text)
            self.assertEqual(item_response.status_code, 200, item_response.text)
            self.assertEqual(date_response.status_code, 200, date_response.text)

            self.assertEqual([deal["listing_id"] for deal in seller_response.json()], [listing_ids["larger_gain"]])
            self.assertEqual([deal["listing_id"] for deal in item_response.json()], [listing_ids["larger_gain"]])

            recent_ids = {deal["listing_id"] for deal in date_response.json()}
            self.assertNotIn(listing_ids["larger_gain"], recent_ids)
            self.assertIn(listing_ids["median"], recent_ids)

    def test_deals_hide_ignored_items_by_default_and_filter_interest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            listing_ids = _seed_deals_fixture(db_path)
            _prefer_item(db_path, 101, "Stave of Shielding", "stave of shielding", "wanted")
            _prefer_item(db_path, 106, "Runed Crown", "runed crown", "ignored")
            app = create_app(db_path)

            with TestClient(app) as client:
                default_response = client.get("/api/deals", params={"server": "frostreaver", "min_discount": 30})
                wanted_response = client.get(
                    "/api/deals",
                    params={"server": "frostreaver", "min_discount": 30, "interest_status": "wanted"},
                )
                ignored_response = client.get(
                    "/api/deals",
                    params={"server": "frostreaver", "min_discount": 30, "interest_status": "ignored"},
                )

            self.assertEqual(default_response.status_code, 200, default_response.text)
            self.assertEqual(wanted_response.status_code, 200, wanted_response.text)
            self.assertEqual(ignored_response.status_code, 200, ignored_response.text)

            default_ids = {deal["listing_id"] for deal in default_response.json()}
            self.assertNotIn(listing_ids["larger_gain"], default_ids)
            self.assertIn(listing_ids["median"], default_ids)

            self.assertEqual([deal["listing_id"] for deal in wanted_response.json()], [listing_ids["median"]])
            self.assertEqual([deal["listing_id"] for deal in ignored_response.json()], [listing_ids["larger_gain"]])
            self.assertEqual(wanted_response.json()[0]["item_preference"], "wanted")
            self.assertEqual(ignored_response.json()[0]["item_preference"], "ignored")

    def test_deals_can_be_sorted_by_supported_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            listing_ids = _seed_deals_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                seller_response = client.get(
                    "/api/deals",
                    params={"server": "frostreaver", "sort_by": "seller", "sort_dir": "asc"},
                )
                date_response = client.get(
                    "/api/deals",
                    params={"server": "frostreaver", "sort_by": "date", "sort_dir": "asc"},
                )
                invalid_response = client.get(
                    "/api/deals",
                    params={"server": "frostreaver", "sort_by": "raw_sql"},
                )

            self.assertEqual(seller_response.status_code, 200, seller_response.text)
            self.assertEqual(date_response.status_code, 200, date_response.text)
            self.assertEqual(invalid_response.status_code, 422)

            self.assertEqual(
                [deal["listing_id"] for deal in seller_response.json()],
                [listing_ids["larger_gain"], listing_ids["median"], listing_ids["p25_fallback"], listing_ids["avg_fallback"]],
            )
            self.assertEqual(
                [deal["listing_id"] for deal in date_response.json()],
                [listing_ids["p25_fallback"], listing_ids["larger_gain"], listing_ids["avg_fallback"], listing_ids["median"]],
            )

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

    def test_deals_exclude_discarded_and_hide_suspect_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            listing_ids = _seed_deals_fixture(db_path)
            _review_listing(db_path, listing_ids["median"], "discarded", "wrong_unit")
            _review_listing(db_path, listing_ids["p25_fallback"], "suspect", "bare_price_extreme_discount")
            app = create_app(db_path)

            with TestClient(app) as client:
                default_response = client.get("/api/deals", params={"server": "frostreaver", "min_discount": 30})
                suspect_response = client.get(
                    "/api/deals",
                    params={"server": "frostreaver", "min_discount": 30, "include_suspect": "true"},
                )

            self.assertEqual(default_response.status_code, 200, default_response.text)
            self.assertEqual(suspect_response.status_code, 200, suspect_response.text)

            default_ids = {deal["listing_id"] for deal in default_response.json()}
            suspect_ids = {deal["listing_id"] for deal in suspect_response.json()}
            self.assertNotIn(listing_ids["median"], default_ids)
            self.assertNotIn(listing_ids["p25_fallback"], default_ids)
            self.assertNotIn(listing_ids["median"], suspect_ids)
            self.assertIn(listing_ids["p25_fallback"], suspect_ids)

    def test_deals_auto_hide_bare_prices_that_look_like_missing_krono_unit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_deals_fixture(db_path)
            suspicious_listing_id = _seed_suspicious_missing_krono_listing(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                default_response = client.get("/api/deals", params={"server": "frostreaver", "min_discount": 0})
                suspect_response = client.get(
                    "/api/deals",
                    params={"server": "frostreaver", "min_discount": 0, "include_suspect": "true"},
                )

            self.assertEqual(default_response.status_code, 200, default_response.text)
            self.assertEqual(suspect_response.status_code, 200, suspect_response.text)

            default_ids = {deal["listing_id"] for deal in default_response.json()}
            self.assertNotIn(suspicious_listing_id, default_ids)

            suspect_deals = {deal["listing_id"]: deal for deal in suspect_response.json()}
            self.assertEqual(suspect_deals[suspicious_listing_id]["review_status"], "suspect")
            self.assertEqual(suspect_deals[suspicious_listing_id]["review_reason_code"], "likely_krono_price_missing_unit")


def _review_listing(db_path: Path, listing_id: int, status: str, reason_code: str) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            """
            INSERT INTO market_listing_reviews (listing_id, status, reason_code)
            VALUES (?, ?, ?)
            """,
            (listing_id, status, reason_code),
        )
        connection.commit()


def _prefer_item(db_path: Path, item_id: int, item_name: str, normalized_name: str, status: str) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            """
            INSERT INTO item_preferences (
                server, preference_key_kind, preference_key, item_id,
                item_name, normalized_item_name, status
            ) VALUES ('frostreaver', 'item_id', ?, ?, ?, ?, ?)
            """,
            (str(item_id), item_id, item_name, normalized_name, status),
        )
        connection.commit()


def _move_listing_timestamp(db_path: Path, listing_id: int, timestamp_modifier: str) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            """
            UPDATE market_listings
            SET timestamp = datetime('now', ?)
            WHERE listing_id = ?
            """,
            (timestamp_modifier, listing_id),
        )
        connection.commit()


def _seed_suspicious_missing_krono_listing(db_path: Path) -> int:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            INSERT INTO items (item_id, name, normalized_name)
            VALUES (109, 'Bo Staff of Trorsmang', 'bo staff of trorsmang')
            """
        )
        connection.execute(
            """
            INSERT INTO market_prices (
                item_id, server, median_pp, p25_pp, avg_pp, sample_size, confidence, last_refresh_at, source
            ) VALUES (109, 'frostreaver', 120817, 118000, 121500, 8, 'high', CURRENT_TIMESTAMP, 'fixture')
            """
        )
        connection.execute(
            """
            INSERT INTO krono_prices (server, price_pp, source, confidence, last_refresh_at)
            VALUES ('frostreaver', 2875, 'fixture', 'high', CURRENT_TIMESTAMP)
            """
        )
        cursor = connection.execute(
            """
            INSERT INTO market_listings (
                server, timestamp, seller, item_name, normalized_item_name, item_id,
                price_raw, price_amount, price_currency, price_pp, source, confidence
            ) VALUES ('frostreaver', datetime('now'), 'TypoSeller', 'Bo Staff of Trorsmang',
                      'bo staff of trorsmang', 109, '42', 42, 'pp', 42, 'eq_log', 'parsed')
            """
        )
        connection.commit()
        return int(cursor.lastrowid)


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
            raw_line = f"[Tue Jun 16 10:00:00 2026] {seller} auctions, 'WTS {item_name} {price_raw}'"
            cursor = connection.execute(
                """
                INSERT INTO market_listings (
                    server, timestamp, seller, item_name, normalized_item_name, item_id,
                    price_raw, price_pp, raw_line, source, confidence
                ) VALUES (?, datetime('now', ?), ?, ?, ?, ?, ?, ?, ?, 'eq_log', 'parsed')
                """,
                (server, timestamp_modifier, seller, item_name, normalized_name, item_id, price_raw, price_pp, raw_line),
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

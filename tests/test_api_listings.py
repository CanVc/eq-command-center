from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from eqmarket.api.app import create_app
from eqmarket.db import init_db


class ApiListingsTests(unittest.TestCase):
    def test_recent_listings_are_sorted_and_include_unresolved_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            listing_ids = _seed_listings_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/listings/recent", params={"server": "Frostreaver", "limit": 10})

            self.assertEqual(response.status_code, 200)
            payload = response.json()

            self.assertEqual(
                [listing["listing_id"] for listing in payload],
                [listing_ids["unresolved"], listing_ids["canonical"], listing_ids["resolved"]],
            )

            self.assertEqual(payload[0]["timestamp"], "2026-06-16 12:00:00")
            self.assertEqual(payload[0]["seller"], "MysterySeller")
            self.assertEqual(payload[0]["item"], {"item_id": None, "name": "Mystery Blade"})
            self.assertIsNone(payload[0]["item_id"])
            self.assertEqual(payload[0]["item_name"], "Mystery Blade")
            self.assertIsNone(payload[0]["price_raw"])
            self.assertIsNone(payload[0]["price_pp"])
            self.assertEqual(payload[0]["source"], "eq_log")
            self.assertEqual(payload[0]["confidence"], "no_price")
            self.assertFalse(payload[0]["resolved"])

            self.assertEqual(payload[1]["item"], {"item_id": 102, "name": "Runed Crown"})
            self.assertEqual(payload[1]["item_name"], "Runed Crown")
            self.assertEqual(payload[1]["price_raw"], "8k")
            self.assertEqual(payload[1]["price_pp"], 8000)
            self.assertTrue(payload[1]["resolved"])

    def test_recent_listings_searches_item_and_seller_then_paginates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            listing_ids = _seed_listings_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                item_response = client.get("/api/listings/recent", params={"server": "frostreaver", "q": "shield"})
                seller_response = client.get("/api/listings/recent", params={"server": "frostreaver", "q": "crownseller"})
                paged_response = client.get(
                    "/api/listings/recent",
                    params={"server": "frostreaver", "limit": 1, "offset": 1},
                )

            self.assertEqual(item_response.status_code, 200)
            self.assertEqual([listing["listing_id"] for listing in item_response.json()], [listing_ids["resolved"]])

            self.assertEqual(seller_response.status_code, 200)
            self.assertEqual([listing["listing_id"] for listing in seller_response.json()], [listing_ids["canonical"]])

            self.assertEqual(paged_response.status_code, 200)
            self.assertEqual([listing["listing_id"] for listing in paged_response.json()], [listing_ids["canonical"]])

    def test_listing_review_can_discard_and_restore_listing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            listing_ids = _seed_listings_fixture(db_path)
            app = create_app(db_path)
            listing_id = listing_ids["resolved"]

            with TestClient(app) as client:
                discard_response = client.put(
                    f"/api/listings/{listing_id}/review",
                    json={"status": "discarded", "reason_code": "wrong_unit", "note": "42 was probably 42kr"},
                )
                listings_response = client.get("/api/listings/recent", params={"server": "frostreaver", "q": "shield"})
                restore_response = client.post(f"/api/listings/{listing_id}/restore")
                missing_response = client.put("/api/listings/999999/review", json={"status": "discarded"})

            self.assertEqual(discard_response.status_code, 200, discard_response.text)
            self.assertEqual(discard_response.json()["status"], "discarded")
            self.assertEqual(discard_response.json()["reason_code"], "wrong_unit")

            self.assertEqual(listings_response.status_code, 200, listings_response.text)
            listing_payload = listings_response.json()[0]
            self.assertEqual(listing_payload["review_status"], "discarded")
            self.assertEqual(listing_payload["review_reason_code"], "wrong_unit")
            self.assertEqual(listing_payload["review_note"], "42 was probably 42kr")

            self.assertEqual(restore_response.status_code, 200, restore_response.text)
            self.assertEqual(restore_response.json()["status"], "active")
            self.assertIsNone(restore_response.json()["reason_code"])
            self.assertEqual(missing_response.status_code, 404)


def _seed_listings_fixture(db_path: Path) -> dict[str, int]:
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
                (102, "Runed Crown", "runed crown"),
                (103, "Other Server Item", "other server item"),
            ],
        )

        listing_rows = [
            (
                "resolved",
                "frostreaver",
                "2026-06-16 10:00:00",
                "Nebblastin",
                "Stave of Shielding",
                "stave of shielding",
                101,
                "4k",
                4000,
                "parsed",
            ),
            (
                "canonical",
                "frostreaver",
                "2026-06-16 11:00:00",
                "CrownSeller",
                "Runed Crown MQ",
                "runed crown mq",
                102,
                "8k",
                8000,
                "parsed",
            ),
            (
                "unresolved",
                "frostreaver",
                "2026-06-16 12:00:00",
                "MysterySeller",
                "Mystery Blade",
                "mystery blade",
                None,
                None,
                None,
                "no_price",
            ),
            (
                "other_server",
                "other",
                "2026-06-16 13:00:00",
                "OtherSeller",
                "Other Server Item",
                "other server item",
                103,
                "1k",
                1000,
                "parsed",
            ),
        ]

        for key, server, timestamp, seller, item_name, normalized_name, item_id, price_raw, price_pp, confidence in listing_rows:
            cursor = connection.execute(
                """
                INSERT INTO market_listings (
                    server, timestamp, seller, item_name, normalized_item_name, item_id,
                    price_raw, price_pp, source, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'eq_log', ?)
                """,
                (server, timestamp, seller, item_name, normalized_name, item_id, price_raw, price_pp, confidence),
            )
            listing_ids[key] = int(cursor.lastrowid)

        connection.commit()

    return listing_ids

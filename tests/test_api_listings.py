from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from eqmarket.api.app import create_app
from eqmarket.db import init_db
from eqmarket.log_importer import insert_listing
from eqmarket.log_parser import ParsedListing


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
            self.assertEqual(payload[0]["item"], {"item_id": None, "name": "Mystery Blade", "sources": []})
            self.assertIsNone(payload[0]["item_id"])
            self.assertEqual(payload[0]["item_name"], "Mystery Blade")
            self.assertIsNone(payload[0]["price_raw"])
            self.assertEqual(
                payload[0]["raw_line"],
                "[Tue Jun 16 10:00:00 2026] MysterySeller auctions, 'WTS Mystery Blade'",
            )
            self.assertIsNone(payload[0]["price_pp"])
            self.assertEqual(payload[0]["source"], "eq_log")
            self.assertEqual(payload[0]["confidence"], "no_price")
            self.assertFalse(payload[0]["resolved"])

            self.assertEqual(payload[1]["item"]["item_id"], 102)
            self.assertEqual(payload[1]["item"]["name"], "Runed Crown")
            self.assertEqual(payload[1]["item"]["sources"][0]["zone"], "Karnor's Castle")
            self.assertEqual(payload[1]["item"]["sources"][0]["npc_name"], "Venril Sathir")
            self.assertEqual(payload[1]["item_name"], "Runed Crown")
            self.assertEqual(payload[1]["price_raw"], "8k")
            self.assertEqual(
                payload[1]["raw_line"],
                "[Tue Jun 16 10:00:00 2026] CrownSeller auctions, 'WTS Runed Crown MQ 8k'",
            )
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

    def test_listing_item_preference_can_ignore_unresolved_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            listing_ids = _seed_listings_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                ignore_response = client.put(
                    f"/api/listings/{listing_ids['unresolved']}/item-preference",
                    json={"status": "ignored"},
                )
                default_response = client.get(
                    "/api/listings/recent",
                    params={"server": "frostreaver", "q": "mystery"},
                )
                ignored_response = client.get(
                    "/api/listings/recent",
                    params={"server": "frostreaver", "q": "mystery", "interest_status": "ignored"},
                )

            self.assertEqual(ignore_response.status_code, 200, ignore_response.text)
            self.assertEqual(ignore_response.json()["status"], "ignored")
            self.assertEqual(ignore_response.json()["preference_key_kind"], "name")
            self.assertEqual(ignore_response.json()["preference_key"], "mystery blade")

            self.assertEqual(default_response.status_code, 200, default_response.text)
            self.assertEqual(default_response.json(), [])

            self.assertEqual(ignored_response.status_code, 200, ignored_response.text)
            self.assertEqual([listing["listing_id"] for listing in ignored_response.json()], [listing_ids["unresolved"]])
            self.assertEqual(ignored_response.json()[0]["item_preference"], "ignored")

    def test_recent_listings_can_filter_by_review_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            listing_ids = _seed_listings_fixture(db_path)
            _review_listing(db_path, listing_ids["resolved"], "suspect", "manual")
            _review_listing(db_path, listing_ids["canonical"], "discarded", "wrong_unit")
            app = create_app(db_path)

            with TestClient(app) as client:
                active_response = client.get(
                    "/api/listings/recent",
                    params={"server": "frostreaver", "review_status": "active"},
                )
                suspect_response = client.get(
                    "/api/listings/recent",
                    params={"server": "frostreaver", "review_status": "suspect"},
                )
                discarded_response = client.get(
                    "/api/listings/recent",
                    params={"server": "frostreaver", "review_status": "discarded"},
                )
                all_response = client.get(
                    "/api/listings/recent",
                    params={"server": "frostreaver", "review_status": "all"},
                )

            self.assertEqual(active_response.status_code, 200, active_response.text)
            self.assertEqual(suspect_response.status_code, 200, suspect_response.text)
            self.assertEqual(discarded_response.status_code, 200, discarded_response.text)
            self.assertEqual(all_response.status_code, 200, all_response.text)

            self.assertEqual([listing["listing_id"] for listing in active_response.json()], [listing_ids["unresolved"]])
            self.assertEqual([listing["listing_id"] for listing in suspect_response.json()], [listing_ids["resolved"]])
            self.assertEqual([listing["listing_id"] for listing in discarded_response.json()], [listing_ids["canonical"]])
            self.assertEqual(
                [listing["listing_id"] for listing in all_response.json()],
                [listing_ids["unresolved"], listing_ids["canonical"], listing_ids["resolved"]],
            )

    def test_discard_similar_creates_rule_and_restore_similar_disables_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            listing_ids = _seed_listings_fixture(db_path)
            similar_id = _insert_market_listing(
                db_path,
                server="frostreaver",
                timestamp="2026-06-16 09:30:00",
                seller="Nebblastin",
                item_id=101,
                item_name="Stave of Shielding",
                normalized_item_name="stave of shielding",
                price_raw="4k",
                price_amount=4,
                price_currency="pp",
                price_pp=4000,
            )
            different_price_id = _insert_market_listing(
                db_path,
                server="frostreaver",
                timestamp="2026-06-16 09:00:00",
                seller="Nebblastin",
                item_id=101,
                item_name="Stave of Shielding",
                normalized_item_name="stave of shielding",
                price_raw="5k",
                price_amount=5,
                price_currency="pp",
                price_pp=5000,
            )
            app = create_app(db_path)

            with TestClient(app) as client:
                discard_response = client.post(
                    f"/api/listings/{listing_ids['resolved']}/discard-similar",
                    json={"reason_code": "wrong_unit", "note": "same seller/item/price"},
                )

            self.assertEqual(discard_response.status_code, 200, discard_response.text)
            discard_payload = discard_response.json()
            self.assertEqual(discard_payload["action"], "discard_similar")
            self.assertEqual(discard_payload["matched_count"], 2)
            self.assertEqual(discard_payload["rule"]["enabled"], True)
            self.assertEqual(discard_payload["rule"]["item_id"], 101)
            self.assertEqual(discard_payload["rule"]["price_currency"], "pp")
            self.assertEqual(discard_payload["rule"]["price_amount"], 4.0)
            self.assertEqual(discard_payload["rule"]["price_pp"], 4000)

            self.assertEqual(_review_statuses(db_path), {
                listing_ids["resolved"]: "discarded",
                similar_id: "discarded",
            })
            self.assertNotIn(different_price_id, _review_statuses(db_path))

            future_id = _insert_listing_through_importer(db_path)
            self.assertEqual(_review_statuses(db_path)[future_id], "discarded")

            with TestClient(app) as client:
                restore_response = client.post(f"/api/listings/{listing_ids['resolved']}/restore-similar")

            self.assertEqual(restore_response.status_code, 200, restore_response.text)
            restore_payload = restore_response.json()
            self.assertEqual(restore_payload["action"], "restore_similar")
            self.assertEqual(restore_payload["disabled_rule_count"], 1)
            self.assertEqual(restore_payload["matched_count"], 3)
            self.assertEqual(restore_payload["restored_count"], 3)
            self.assertEqual(_enabled_rule_count(db_path), 0)
            self.assertEqual(_review_statuses(db_path)[listing_ids["resolved"]], "active")
            self.assertEqual(_review_statuses(db_path)[similar_id], "active")
            self.assertEqual(_review_statuses(db_path)[future_id], "active")

            next_future_id = _insert_listing_through_importer(db_path, raw_line="future after restore")
            self.assertNotIn(next_future_id, _review_statuses(db_path))

    def test_discard_similar_krono_rule_matches_seen_krono_amount_not_converted_pp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_listings_fixture(db_path)
            first_id = _insert_market_listing(
                db_path,
                server="frostreaver",
                timestamp="2026-06-16 09:00:00",
                seller="KronoSeller",
                item_id=101,
                item_name="Stave of Shielding",
                normalized_item_name="stave of shielding",
                price_raw="1kr",
                price_amount=1,
                price_currency="krono",
                price_pp=10000,
            )
            second_id = _insert_market_listing(
                db_path,
                server="frostreaver",
                timestamp="2026-06-16 09:05:00",
                seller="KronoSeller",
                item_id=101,
                item_name="Stave of Shielding",
                normalized_item_name="stave of shielding",
                price_raw="1kr",
                price_amount=1,
                price_currency="krono",
                price_pp=11000,
            )
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.post(f"/api/listings/{first_id}/discard-similar", json={"reason_code": "manual"})

            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertEqual(payload["matched_count"], 2)
            self.assertIsNone(payload["rule"]["price_pp"])
            self.assertEqual(_review_statuses(db_path)[first_id], "discarded")
            self.assertEqual(_review_statuses(db_path)[second_id], "discarded")


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


def _insert_market_listing(
    db_path: Path,
    *,
    server: str,
    timestamp: str,
    seller: str,
    item_id: int,
    item_name: str,
    normalized_item_name: str,
    price_raw: str,
    price_amount: float,
    price_currency: str,
    price_pp: int,
) -> int:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.execute(
            """
            INSERT INTO market_listings (
                server, timestamp, seller, item_name, normalized_item_name, item_id,
                price_raw, price_amount, price_currency, price_pp, source, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'eq_log', 'parsed')
            """,
            (
                server,
                timestamp,
                seller,
                item_name,
                normalized_item_name,
                item_id,
                price_raw,
                price_amount,
                price_currency,
                price_pp,
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def _insert_listing_through_importer(db_path: Path, raw_line: str = "future same listing") -> int:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        inserted, _pending = insert_listing(
            connection,
            "frostreaver",
            ParsedListing(
                timestamp="2026-06-16 14:00:00",
                seller="Nebblastin",
                item_name="Stave of Shielding",
                price_raw="4k",
                price_amount=4,
                price_currency="pp",
                price_pp=4000,
                raw_line=raw_line,
                item_id=101,
            ),
        )
        self_check_row = connection.execute("SELECT max(listing_id) FROM market_listings").fetchone()
        connection.commit()
    if not inserted:
        raise AssertionError("fixture future listing was not inserted")
    return int(self_check_row[0])


def _review_statuses(db_path: Path) -> dict[int, str]:
    with closing(sqlite3.connect(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT listing_id, status
            FROM market_listing_reviews
            ORDER BY listing_id
            """
        ).fetchall()
    return {int(row[0]): str(row[1]) for row in rows}


def _enabled_rule_count(db_path: Path) -> int:
    with closing(sqlite3.connect(db_path)) as connection:
        row = connection.execute(
            """
            SELECT count(*)
            FROM market_listing_discard_rules
            WHERE enabled = 1
            """
        ).fetchone()
    return int(row[0])


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
        connection.executemany(
            """
            INSERT INTO item_sources (
                item_id, data_source, source_url, external_item_id, content_type,
                zone, source_area, npc_name, last_checked_at, confidence
            ) VALUES (?, 'fixture', ?, ?, 'raid', ?, NULL, ?, '2026-06-16 09:00:00', 'high')
            """,
            [
                (101, "https://example.test/stave", "101", "Old Sebilis", "myconid spore king"),
                (102, "https://example.test/crown", "102", "Karnor's Castle", "Venril Sathir"),
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
                4,
                "pp",
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
                8,
                "pp",
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
                1,
                "pp",
                1000,
                "parsed",
            ),
        ]

        for (
            key,
            server,
            timestamp,
            seller,
            item_name,
            normalized_name,
            item_id,
            price_raw,
            price_amount,
            price_currency,
            price_pp,
            confidence,
        ) in listing_rows:
            price_suffix = f" {price_raw}" if price_raw is not None else ""
            raw_line = f"[Tue Jun 16 10:00:00 2026] {seller} auctions, 'WTS {item_name}{price_suffix}'"
            cursor = connection.execute(
                """
                INSERT INTO market_listings (
                    server, timestamp, seller, item_name, normalized_item_name, item_id,
                    price_raw, price_amount, price_currency, price_pp, raw_line, source, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'eq_log', ?)
                """,
                (
                    server,
                    timestamp,
                    seller,
                    item_name,
                    normalized_name,
                    item_id,
                    price_raw,
                    price_amount,
                    price_currency,
                    price_pp,
                    raw_line,
                    confidence,
                ),
            )
            listing_ids[key] = int(cursor.lastrowid)

        connection.commit()

    return listing_ids

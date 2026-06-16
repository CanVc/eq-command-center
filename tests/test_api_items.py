from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from eqmarket.api.app import create_app
from eqmarket.db import init_db


class ApiItemsTests(unittest.TestCase):
    def test_search_returns_matching_item_names_and_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_items_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/items/search", params={"q": "stave"})

            self.assertEqual(response.status_code, 200)
            payload = response.json()

            self.assertEqual(payload[0]["item_id"], 101)
            self.assertEqual(payload[0]["name"], "Stave of Shielding")
            self.assertIsNone(payload[0]["icon_url"])

    def test_item_detail_returns_stats_and_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_items_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/items/101")

            self.assertEqual(response.status_code, 200)
            payload = response.json()

            self.assertEqual(payload["item_id"], 101)
            self.assertEqual(payload["name"], "Stave of Shielding")
            self.assertIsNone(payload["icon_url"])
            self.assertEqual(payload["slot"], "PRIMARY")
            self.assertEqual(payload["stats"]["hp"], 55)
            self.assertEqual(payload["stats"]["str"], 4)
            self.assertEqual(payload["combat"]["damage"], 12)
            self.assertEqual(payload["combat"]["delay"], 30)
            self.assertEqual(payload["combat"]["ratio"], 0.4)
            self.assertEqual(payload["effects"][0]["spell"], {"spell_id": 1806, "name": "Fungal Regrowth", "spell_type": "Beneficial", "target_type": "Self", "skill": "Alteration"})
            self.assertEqual(payload["effects"][0]["description"], "Fungal Regrowth")

    def test_prices_return_market_payload_with_reference_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_items_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/items/101/prices", params={"server": "Frostreaver"})

            self.assertEqual(response.status_code, 200)
            payload = response.json()

            self.assertEqual(payload["item_id"], 101)
            self.assertEqual(payload["server"], "frostreaver")
            self.assertEqual(payload["market_price_pp"], 10000)
            self.assertEqual(payload["market_price_source"], "avg_pp")
            self.assertEqual(payload["median_pp"], 0)
            self.assertEqual(payload["p25_pp"], 8000)
            self.assertEqual(payload["p75_pp"], 12000)
            self.assertEqual(payload["avg_pp"], 10000)
            self.assertEqual(payload["sample_size"], 3)
            self.assertEqual(payload["confidence"], "low")

    def test_item_listings_are_filtered_by_item_and_server(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            listing_ids = _seed_items_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/items/101/listings", params={"server": "frostreaver", "limit": 1})

            self.assertEqual(response.status_code, 200)
            payload = response.json()

            self.assertEqual([listing["listing_id"] for listing in payload], [listing_ids["latest_stave"]])
            self.assertEqual(payload[0]["item"], {"item_id": 101, "name": "Stave of Shielding"})
            self.assertEqual(payload[0]["listed_item_name"], "Stave of Shielding MQ")
            self.assertEqual(payload[0]["price_raw"], "42k")
            self.assertEqual(payload[0]["price_pp"], 42000)
            self.assertTrue(payload[0]["resolved"])

    def test_tooltip_by_id_contains_key_stats_prices_and_last_seen(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_items_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/items/101/tooltip", params={"server": "frostreaver"})

            self.assertEqual(response.status_code, 200)
            payload = response.json()

            self.assertEqual(payload["item_id"], 101)
            self.assertEqual(payload["name"], "Stave of Shielding")
            self.assertIsNone(payload["icon_url"])
            self.assertEqual(payload["slot"], "PRIMARY")
            self.assertEqual(payload["classes"], "WAR PAL RNG SHD MNK BRD ROG")
            self.assertEqual(payload["ac"], 12)
            self.assertEqual(payload["hp"], 55)
            self.assertEqual(payload["mana"], 10)
            self.assertEqual(payload["damage"], 12)
            self.assertEqual(payload["delay"], 30)
            self.assertEqual(payload["ratio"], 0.4)
            self.assertEqual(payload["flags"], "MAGIC")
            self.assertEqual(payload["market_price_pp"], 10000)
            self.assertEqual(payload["market_price_source"], "avg_pp")
            self.assertEqual(payload["last_seen_pp"], 42000)
            self.assertEqual(payload["last_seen_at"], "2026-06-16 12:00:00")
            self.assertEqual(payload["effects"][0]["spell"]["name"], "Fungal Regrowth")

    def test_tooltip_fallback_by_name_uses_normalized_item_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_items_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get(
                    "/api/items/tooltip",
                    params={"name": "  STAVE   OF   SHIELDING  ", "server": "frostreaver"},
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["item_id"], 101)

    def test_absent_item_returns_clean_404(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                id_response = client.get("/api/items/999")
                name_response = client.get("/api/items/tooltip", params={"name": "Missing Item"})

            self.assertEqual(id_response.status_code, 404)
            self.assertEqual(id_response.json(), {"detail": "Item not found"})
            self.assertEqual(name_response.status_code, 404)
            self.assertEqual(name_response.json(), {"detail": "Item not found"})


def _seed_items_fixture(db_path: Path) -> dict[str, int]:
    listing_ids: dict[str, int] = {}

    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executemany(
            """
            INSERT INTO items (
                item_id, name, normalized_name, item_type, slot, classes, races,
                ac, hp, mana, endurance, hp_regen, mana_regen, endurance_regen,
                astr, asta, aagi, adex, awis, aint, acha,
                sv_magic, sv_fire, sv_cold, sv_poison, sv_disease,
                damage, delay, ratio, haste, required_level, recommended_level,
                icon_id, flags, source_primary, last_imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    101,
                    "Stave of Shielding",
                    "stave of shielding",
                    "weapon",
                    "PRIMARY",
                    "WAR PAL RNG SHD MNK BRD ROG",
                    "ALL",
                    12,
                    55,
                    10,
                    0,
                    1,
                    0,
                    0,
                    4,
                    5,
                    6,
                    7,
                    8,
                    9,
                    10,
                    11,
                    12,
                    13,
                    14,
                    15,
                    12,
                    30,
                    0.4,
                    0,
                    45,
                    50,
                    601,
                    "MAGIC",
                    "fixture",
                    "2026-06-16 09:00:00",
                ),
                (
                    102,
                    "Runed Crown",
                    "runed crown",
                    "armor",
                    "HEAD",
                    "ALL",
                    "ALL",
                    20,
                    80,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "MAGIC",
                    "fixture",
                    "2026-06-16 09:00:00",
                ),
                (
                    103,
                    "Other Server Item",
                    "other server item",
                    "armor",
                    "CHEST",
                    "ALL",
                    "ALL",
                    1,
                    2,
                    3,
                    4,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "fixture",
                    "2026-06-16 09:00:00",
                ),
            ],
        )
        connection.executemany(
            """
            INSERT INTO market_prices (
                item_id, server, median_pp, p25_pp, p75_pp, avg_pp, min_pp, max_pp,
                sample_size, confidence, last_refresh_at, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (101, "frostreaver", 0, 8000, 12000, 10000, 7000, 15000, 3, "low", "2026-06-16 09:30:00", "fixture"),
                (102, "frostreaver", 90000, 75000, 110000, 95000, 70000, 120000, 20, "high", "2026-06-16 09:30:00", "fixture"),
                (103, "other", 5000, 4000, 6000, 5500, 3500, 6500, 5, "medium", "2026-06-16 09:30:00", "fixture"),
            ],
        )
        connection.execute(
            """
            INSERT INTO spells (
                spell_id, name, normalized_name, spell_type, target_type, skill, source_server
            ) VALUES (1806, 'Fungal Regrowth', 'fungal regrowth', 'Beneficial', 'Self', 'Alteration', 'Live')
            """
        )
        connection.execute(
            """
            INSERT INTO item_effects (
                item_id, effect_slot, spell_id, trigger_type, effect_type_raw,
                cast_time_ms, effective_level
            ) VALUES (101, 0, 1806, 'worn', 1, 0, 0)
            """
        )

        listing_rows = [
            (
                "older_stave",
                "frostreaver",
                "2026-06-16 11:00:00",
                "OlderSeller",
                "Stave of Shielding",
                "stave of shielding",
                101,
                "50k",
                50000,
            ),
            (
                "latest_stave",
                "frostreaver",
                "2026-06-16 12:00:00",
                "LatestSeller",
                "Stave of Shielding MQ",
                "stave of shielding mq",
                101,
                "42k",
                42000,
            ),
            (
                "other_item",
                "frostreaver",
                "2026-06-16 13:00:00",
                "OtherSeller",
                "Runed Crown",
                "runed crown",
                102,
                "80k",
                80000,
            ),
            (
                "other_server",
                "other",
                "2026-06-16 14:00:00",
                "RemoteSeller",
                "Stave of Shielding",
                "stave of shielding",
                101,
                "1k",
                1000,
            ),
        ]

        for key, server, timestamp, seller, item_name, normalized_name, item_id, price_raw, price_pp in listing_rows:
            cursor = connection.execute(
                """
                INSERT INTO market_listings (
                    server, timestamp, seller, item_name, normalized_item_name, item_id,
                    price_raw, price_pp, source, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'eq_log', 'parsed')
                """,
                (server, timestamp, seller, item_name, normalized_name, item_id, price_raw, price_pp),
            )
            listing_ids[key] = int(cursor.lastrowid)

        connection.commit()

    return listing_ids

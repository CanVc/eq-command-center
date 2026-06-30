from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from eqmarket.api.app import create_app
from eqmarket.db import init_db


class ApiCharacterUpgradesTests(unittest.TestCase):
    def test_character_upgrades_compare_owned_listings_and_market_by_slot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_upgrade_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get(
                    "/api/characters/Dreadnought/upgrades",
                    params={"slot": "LEGS", "source": "all", "max_price_pp": 20000, "stats": "ac,hp"},
                )

            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertEqual(payload["character_name"], "Dreadnought")
            self.assertEqual(payload["stats"], ["ac", "hp"])
            self.assertTrue(payload["better_only"])
            self.assertEqual(payload["slot"], "LEGS")

            candidates = payload["candidates"]
            candidate_names = {candidate["candidate"]["name"] for candidate in candidates}
            self.assertIn("Banked Cobalt Greaves", candidate_names)
            self.assertIn("Auction Greaves", candidate_names)
            self.assertIn("TLP Greaves", candidate_names)
            self.assertNotIn("Necromancer Greaves", candidate_names)
            self.assertNotIn("Ignored Greaves", candidate_names)
            self.assertNotIn("Expensive Greaves", candidate_names)

            banked = next(candidate for candidate in candidates if candidate["candidate"]["name"] == "Banked Cobalt Greaves")
            self.assertEqual(banked["source"], "owned")
            self.assertEqual(banked["cost_pp"], 0)
            self.assertEqual(banked["areas"], ["bank"])
            self.assertEqual(banked["area_quantities"], {"bank": 1})
            self.assertEqual(banked["current_item"]["name"], "Rusted Greaves")
            self.assertEqual(banked["candidate"]["sources"][0]["zone"], "Kael Drakkel")
            self.assertEqual(banked["candidate"]["sources"][0]["npc_name"], "Derakor the Vindicator")
            self.assertGreater(banked["deltas"]["ac"], 0)
            self.assertGreater(banked["deltas"]["hp"], 0)
            self.assertGreater(banked["score"], 0)

            listing = next(candidate for candidate in candidates if candidate["candidate"]["name"] == "Auction Greaves")
            self.assertEqual(listing["source"], "local_listing")
            self.assertEqual(listing["cost_pp"], 8000)
            self.assertEqual(listing["listing"]["seller"], "Sellerone")
            self.assertEqual(listing["candidate"]["sources"][0]["zone"], "Temple of Veeshan")
            self.assertEqual(listing["candidate"]["sources"][0]["npc_name"], "Aaryonar")

            market = next(candidate for candidate in candidates if candidate["candidate"]["name"] == "TLP Greaves")
            self.assertEqual(market["source"], "market_price")
            self.assertEqual(market["cost_pp"], 12000)
            self.assertEqual(market["price_source"], "median_pp")
            self.assertEqual(market["candidate"]["sources"][0]["zone"], "Sleeper's Tomb")
            self.assertEqual(market["candidate"]["sources"][0]["npc_name"], "The Progenitor")

    def test_character_upgrades_source_budget_and_slot_filters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_upgrade_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                owned_response = client.get(
                    "/api/characters/Dreadnought/upgrades",
                    params={"slot": "LEGS", "source": "owned", "max_price_pp": 1},
                )
                market_response = client.get(
                    "/api/characters/Dreadnought/upgrades",
                    params={"slot": "LEGS", "source": "market", "max_price_pp": 9000},
                )
                primary_response = client.get(
                    "/api/characters/Dreadnought/upgrades",
                    params={"slot": "PRIMARY", "source": "all"},
                )

            self.assertEqual(owned_response.status_code, 200, owned_response.text)
            self.assertEqual(market_response.status_code, 200, market_response.text)
            self.assertEqual(primary_response.status_code, 200, primary_response.text)

            self.assertEqual(
                {candidate["source"] for candidate in owned_response.json()["candidates"]},
                {"owned"},
            )
            self.assertEqual(
                {candidate["candidate"]["name"] for candidate in market_response.json()["candidates"]},
                {"Auction Greaves", "Banked Cobalt Greaves"},
            )
            self.assertEqual(
                {candidate["source"] for candidate in market_response.json()["candidates"]},
                {"local_listing", "market_price"},
            )
            self.assertEqual(
                {candidate["candidate"]["name"] for candidate in primary_response.json()["candidates"]},
                {"Obsidian Sword"},
            )

    def test_unknown_character_class_does_not_filter_every_lucy_numeric_class(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_upgrade_fixture(db_path)
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    "UPDATE characters SET character_class = 'UNKNOWN' WHERE character_name = 'Dreadnought'"
                )
                connection.commit()
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get(
                    "/api/characters/Dreadnought/upgrades",
                    params={"slot": "LEGS", "source": "market", "stats": "ac,hp"},
                )

            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertEqual(payload["character_class"], "UNKNOWN")
            self.assertGreater(payload["candidate_count"], 0)
            candidate_names = {candidate["candidate"]["name"] for candidate in payload["candidates"]}
            self.assertIn("Auction Greaves", candidate_names)
            self.assertNotIn("Necromancer Greaves", candidate_names)
            self.assertEqual(payload["effective_classes"], ["SHD"])

    def test_character_upgrades_item_type_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_upgrade_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                armor_response = client.get(
                    "/api/characters/Dreadnought/upgrades",
                    params={"slot": "LEGS", "source": "all", "item_type": "Armor", "stats": "ac,hp"},
                )
                weapon_legs_response = client.get(
                    "/api/characters/Dreadnought/upgrades",
                    params={"slot": "LEGS", "source": "all", "item_type": "Weapon", "stats": "ac,hp"},
                )
                weapon_primary_response = client.get(
                    "/api/characters/Dreadnought/upgrades",
                    params={"slot": "PRIMARY", "source": "all", "item_type": "Weapon", "stats": "ac,hp"},
                )
                warrior_response = client.get(
                    "/api/characters/Dreadnought/upgrades",
                    params={"slot": "LEGS", "source": "all", "class_filter": "WAR", "stats": "ac,hp"},
                )

            self.assertEqual(armor_response.status_code, 200, armor_response.text)
            self.assertEqual(weapon_legs_response.status_code, 200, weapon_legs_response.text)
            self.assertEqual(weapon_primary_response.status_code, 200, weapon_primary_response.text)
            self.assertEqual(warrior_response.status_code, 200, warrior_response.text)
            self.assertEqual(armor_response.json()["item_type"], "Armor")
            self.assertEqual(weapon_legs_response.json()["candidates"], [])
            self.assertEqual(
                {candidate["candidate"]["name"] for candidate in armor_response.json()["candidates"]},
                {"Banked Cobalt Greaves", "Auction Greaves", "TLP Greaves", "Expensive Greaves"},
            )
            self.assertEqual(
                {candidate["candidate"]["name"] for candidate in weapon_primary_response.json()["candidates"]},
                {"Obsidian Sword"},
            )
            self.assertEqual(warrior_response.json()["class_filter"], "WAR")
            self.assertEqual(warrior_response.json()["effective_classes"], ["WAR"])
            self.assertEqual(
                {candidate["candidate"]["name"] for candidate in warrior_response.json()["candidates"]},
                {"Banked Cobalt Greaves"},
            )

    def test_character_upgrades_can_rank_tradeoffs_when_better_only_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_upgrade_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                strict_response = client.get(
                    "/api/characters/Dreadnought/upgrades",
                    params={"slot": "LEGS", "source": "market", "stats": "sv_fire,ac", "better_only": "true"},
                )
                tradeoff_response = client.get(
                    "/api/characters/Dreadnought/upgrades",
                    params={"slot": "LEGS", "source": "market", "stats": "sv_fire,ac", "better_only": "false"},
                )

            self.assertEqual(strict_response.status_code, 200, strict_response.text)
            self.assertEqual(tradeoff_response.status_code, 200, tradeoff_response.text)

            strict_names = {candidate["candidate"]["name"] for candidate in strict_response.json()["candidates"]}
            self.assertNotIn("Charred Resist Greaves", strict_names)

            tradeoff_payload = tradeoff_response.json()
            self.assertEqual(tradeoff_payload["stats"], ["sv_fire", "ac"])
            self.assertFalse(tradeoff_payload["better_only"])
            tradeoff_candidates = tradeoff_payload["candidates"]
            self.assertEqual(tradeoff_candidates[0]["candidate"]["name"], "Charred Resist Greaves")
            self.assertGreater(tradeoff_candidates[0]["deltas"]["sv_fire"], 0)
            self.assertLess(tradeoff_candidates[0]["deltas"]["ac"], 0)

    def test_missing_character_upgrade_lookup_returns_clean_404(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/characters/Missing/upgrades")

            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json(), {"detail": "Character not found"})


def _seed_upgrade_fixture(db_path: Path) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executemany(
            """
            INSERT INTO items (
                item_id, name, normalized_name, item_type, slot, classes, races,
                ac, hp, mana, endurance, astr, asta, aagi, adex, awis, aint, acha,
                sv_magic, sv_fire, sv_cold, sv_poison, sv_disease,
                damage, delay, ratio, haste, icon_id, flags, source_primary, last_imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'ALL', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (100, "Rusted Greaves", "rusted greaves", "armor", "262144", "16", 5, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, None, None, None, None, 1001, "MAGIC", "lucy", "2026-06-20 10:00:00"),
                (101, "Bronze Sword", "bronze sword", "weapon", "8192", "16", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 30, 0.333, 0, 1002, "MAGIC", "lucy", "2026-06-20 10:00:00"),
                (201, "Banked Cobalt Greaves", "banked cobalt greaves", "armor", "262144", "21", 18, 55, 5, 0, 1, 2, 3, 4, 0, 0, 0, 5, 5, 5, 5, 5, None, None, None, None, 1003, "MAGIC", "lucy", "2026-06-20 10:00:00"),
                (202, "Necromancer Greaves", "necromancer greaves", "armor", "262144", "1024", 50, 200, 200, 0, 0, 0, 0, 0, 0, 0, 0, 20, 20, 20, 20, 20, None, None, None, None, 1004, "MAGIC", "lucy", "2026-06-20 10:00:00"),
                (203, "Ignored Greaves", "ignored greaves", "armor", "262144", "16", 40, 150, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 10, 10, 10, 10, None, None, None, None, 1005, "MAGIC", "lucy", "2026-06-20 10:00:00"),
                (301, "TLP Greaves", "tlp greaves", "armor", "262144", "16", 24, 90, 20, 0, 0, 0, 0, 0, 0, 0, 0, 8, 8, 8, 8, 8, None, None, None, None, 1006, "MAGIC", "lucy", "2026-06-20 10:00:00"),
                (401, "Auction Greaves", "auction greaves", "armor", "262144", "16", 22, 80, 10, 0, 0, 0, 0, 0, 0, 0, 0, 8, 8, 8, 8, 8, None, None, None, None, 1007, "MAGIC", "lucy", "2026-06-20 10:00:00"),
                (402, "Expensive Greaves", "expensive greaves", "armor", "262144", "16", 60, 250, 40, 0, 0, 0, 0, 0, 0, 0, 0, 20, 20, 20, 20, 20, None, None, None, None, 1008, "MAGIC", "lucy", "2026-06-20 10:00:00"),
                (403, "Charred Resist Greaves", "charred resist greaves", "armor", "262144", "16", 1, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 30, 1, 1, 1, None, None, None, None, 1010, "MAGIC", "lucy", "2026-06-20 10:00:00"),
                (501, "Obsidian Sword", "obsidian sword", "weapon", "8192", "16", 0, 25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 18, 30, 0.6, 0, 1009, "MAGIC", "lucy", "2026-06-20 10:00:00"),
            ],
        )
        connection.execute(
            """
            INSERT INTO characters (character_name, character_class, level, server)
            VALUES ('Dreadnought', 'SHD', 60, 'frostreaver')
            """
        )
        connection.executemany(
            """
            INSERT INTO item_sources (
                item_id, data_source, source_url, external_item_id, content_type,
                zone, source_area, npc_name, last_checked_at, confidence
            ) VALUES (?, 'fixture', ?, ?, 'raid', ?, NULL, ?, '2026-06-20 10:30:00', 'high')
            """,
            [
                (201, "https://example.test/cobalt-greaves", "201", "Kael Drakkel", "Derakor the Vindicator"),
                (301, "https://example.test/tlp-greaves", "301", "Sleeper's Tomb", "The Progenitor"),
                (401, "https://example.test/auction-greaves", "401", "Temple of Veeshan", "Aaryonar"),
            ],
        )
        connection.execute(
            """
            INSERT INTO inventory_imports (
                inventory_import_id, character_name, server, source_file, source_hash,
                parser_version, rows_seen, rows_imported, equipment_items_imported,
                inventory_items_imported, status
            ) VALUES (1, 'Dreadnought', 'frostreaver', 'fixture.txt', 'hash', 'fixture', 10, 10, 2, 4, 'completed')
            """
        )
        connection.executemany(
            """
            INSERT INTO character_equipment (
                character_name, slot, slot_index, item_id, item_name, raw_item_name,
                normalized_item_name, inventory_import_id, server, raw_location, quantity, slots
            ) VALUES ('Dreadnought', ?, 1, ?, ?, ?, ?, 1, 'frostreaver', ?, 1, ?)
            """,
            [
                ("LEGS", 100, "Rusted Greaves", "Rusted Greaves", "rusted greaves", "Legs", "262144"),
                ("PRIMARY", 101, "Bronze Sword", "Bronze Sword", "bronze sword", "Primary", "8192"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO character_inventory_items (
                character_name, server, inventory_import_id, area, raw_location,
                item_id, item_name, raw_item_name, normalized_item_name, quantity, slots
            ) VALUES ('Dreadnought', 'frostreaver', 1, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            [
                ("bank", "Bank1", 201, "Banked Cobalt Greaves", "Banked Cobalt Greaves", "banked cobalt greaves", "262144"),
                ("bank", "Bank2", 202, "Necromancer Greaves", "Necromancer Greaves", "necromancer greaves", "262144"),
                ("bank", "Bank3", 203, "Ignored Greaves", "Ignored Greaves", "ignored greaves", "262144"),
                ("carried", "General1", 501, "Obsidian Sword", "Obsidian Sword", "obsidian sword", "8192"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO market_prices (
                item_id, server, median_pp, p25_pp, p75_pp, avg_pp, sample_size, confidence, last_refresh_at, source
            ) VALUES (?, 'frostreaver', ?, ?, ?, ?, ?, ?, '2026-06-21 10:00:00', ?)
            """,
            [
                (201, 3000, 2500, 3500, 3100, 4, "medium", "tlp_auctions_history"),
                (301, 12000, 10000, 15000, 12500, 8, "high", "tlp_auctions_history"),
                (401, 14000, 12000, 18000, 15000, 6, "medium", "tlp_auctions_history"),
                (402, 50000, 45000, 60000, 52000, 4, "medium", "tlp_auctions_history"),
                (403, 4000, 3500, 4500, 3900, 4, "medium", "tlp_auctions_history"),
                (501, 9000, 7500, 11000, 9200, 5, "medium", "tlp_auctions_history"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO market_listings (
                server, timestamp, seller, item_name, normalized_item_name, item_id,
                price_raw, price_amount, price_currency, price_pp, raw_line, source, confidence, seen_hash
            ) VALUES ('frostreaver', CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, 'pp', ?, ?, 'eq_log', 'parsed', ?)
            """,
            [
                ("Sellerone", "Auction Greaves", "auction greaves", 401, "8k", 8000, 8000, "Sellerone auctions Auction Greaves for 8k", "listing-401"),
                ("Sellertwo", "Expensive Greaves", "expensive greaves", 402, "50k", 50000, 50000, "Sellertwo auctions Expensive Greaves for 50k", "listing-402"),
            ],
        )
        connection.execute(
            """
            INSERT INTO inventory_item_decisions (
                server, scope, scope_key, character_name, item_id, item_name,
                normalized_item_name, status
            ) VALUES ('frostreaver', 'character', 'dreadnought', 'Dreadnought', 203, 'Ignored Greaves', 'ignored greaves', 'ignore')
            """
        )
        connection.commit()


if __name__ == "__main__":
    unittest.main()

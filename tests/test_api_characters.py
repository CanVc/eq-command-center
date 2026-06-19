from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from eqmarket.api.app import create_app
from eqmarket.db import init_db


class ApiCharactersTests(unittest.TestCase):
    def test_character_inventory_contracts_cover_paperdoll_inventory_and_imports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_character_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                characters_response = client.get("/api/characters", params={"server": "Frostreaver"})
                detail_response = client.get("/api/characters/dreadnought")
                equipment_response = client.get("/api/characters/Dreadnought/equipment")
                carried_response = client.get(
                    "/api/characters/Dreadnought/inventory",
                    params={"area": "carried", "include_locations": "true"},
                )
                all_inventory_response = client.get("/api/characters/Dreadnought/inventory")
                imports_response = client.get("/api/characters/Dreadnought/imports")

            for response in [
                characters_response,
                detail_response,
                equipment_response,
                carried_response,
                all_inventory_response,
                imports_response,
            ]:
                self.assertEqual(response.status_code, 200, response.text)

            characters = characters_response.json()
            self.assertEqual(len(characters), 1)
            character = characters[0]
            self.assertTrue(
                {
                    "character_name",
                    "server",
                    "character_class",
                    "level",
                    "last_imported_at",
                    "last_import",
                    "freshness",
                    "equipment_item_count",
                    "inventory_item_count",
                    "inventory_quantity",
                    "starter_item_count",
                    "distinct_item_count",
                    "unenriched_item_count",
                    "unpriced_item_count",
                }.issubset(character)
            )
            self.assertEqual(character["character_name"], "Dreadnought")
            self.assertEqual(character["server"], "frostreaver")
            self.assertEqual(character["character_class"], "SHD")
            self.assertEqual(character["level"], 60)
            self.assertEqual(character["last_import"]["inventory_import_id"], 2)
            self.assertEqual(character["equipment_item_count"], 2)
            self.assertEqual(character["inventory_item_count"], 4)
            self.assertEqual(character["inventory_quantity"], 12)
            self.assertEqual(character["starter_item_count"], 2)
            self.assertEqual(character["distinct_item_count"], 5)
            self.assertEqual(character["unenriched_item_count"], 3)
            self.assertEqual(character["unpriced_item_count"], 3)

            detail = detail_response.json()
            self.assertEqual(detail["character_name"], "Dreadnought")
            self.assertTrue(detail["freshness"]["imported"])
            self.assertEqual([row["inventory_import_id"] for row in detail["recent_imports"]], [2, 1])

            equipment = equipment_response.json()
            self.assertIn("EAR_1", equipment["slot_order"])
            self.assertIn("EAR_2", equipment["slot_order"])
            self.assertIn("WRIST_1", equipment["slots"])
            self.assertIsNone(equipment["slots"]["WRIST_1"]["item"])

            starter_ear = equipment["slots"]["EAR_1"]["item"]
            self.assertEqual(starter_ear["item_id"], 1001)
            self.assertEqual(starter_ear["name"], "Pearl Earring")
            self.assertEqual(starter_ear["raw_item_name"], "Pearl Earring*")
            self.assertTrue(starter_ear["is_starter_item"])
            self.assertTrue(starter_ear["is_no_trade_import"])
            self.assertFalse(starter_ear["enriched"])
            self.assertEqual(starter_ear["enrichment_status"], "inventory_stub")
            self.assertFalse(starter_ear["has_price"])
            self.assertEqual(starter_ear["slot_mask"], 2)
            self.assertEqual(starter_ear["slot_labels"], ["EAR"])

            enriched_ear = equipment["slots"]["EAR_2"]["item"]
            self.assertEqual(enriched_ear["item_id"], 1002)
            self.assertTrue(enriched_ear["enriched"])
            self.assertTrue(enriched_ear["has_price"])
            self.assertEqual(enriched_ear["price"]["market_price_pp"], 1000)
            self.assertEqual(enriched_ear["stats"]["hp"], 20)

            carried = carried_response.json()
            self.assertEqual(carried["area"], "carried")
            self.assertTrue(carried["include_locations"])
            self.assertEqual(carried["item_count"], 1)
            self.assertEqual(carried["location_count"], 2)
            self.assertEqual(carried["total_quantity"], 5)
            coral = carried["items"][0]
            self.assertEqual(coral["item_id"], 2001)
            self.assertEqual(coral["quantity"], 5)
            self.assertEqual(coral["areas"], ["carried"])
            self.assertEqual(coral["area_quantities"], {"carried": 5})
            self.assertEqual([location["raw_location"] for location in coral["locations"]], ["General 1-Slot1", "General 2-Slot1"])
            self.assertTrue(coral["has_price"])
            self.assertEqual(coral["item"]["price"]["market_price_pp"], 500)

            all_inventory = all_inventory_response.json()
            self.assertEqual(all_inventory["area"], "all")
            self.assertFalse(all_inventory["include_locations"])
            self.assertEqual(all_inventory["item_count"], 3)
            self.assertEqual(all_inventory["total_quantity"], 12)
            self.assertNotIn(8001, {item["item_id"] for item in all_inventory["items"]})
            training_dagger = next(item for item in all_inventory["items"] if item["item_id"] == 9001)
            self.assertTrue(training_dagger["is_starter_item"])
            self.assertTrue(training_dagger["is_no_trade_import"])
            self.assertFalse(training_dagger["has_price"])
            self.assertEqual(training_dagger["item"]["raw_item_name"], "Training Dagger*")
            self.assertIsNone(training_dagger["locations"])

            imports = imports_response.json()
            self.assertEqual(imports["character_name"], "Dreadnought")
            self.assertEqual([row["inventory_import_id"] for row in imports["imports"]], [2, 1])
            self.assertEqual(imports["imports"][0]["rows_imported"], 7)

    def test_missing_character_returns_clean_404(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/characters/Missing")

            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json(), {"detail": "Character not found"})


def _seed_character_fixture(db_path: Path) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executemany(
            """
            INSERT INTO items (
                item_id, name, normalized_name, item_type, slot, classes, races,
                ac, hp, mana, endurance, astr, asta, aagi, adex, awis, aint, acha,
                damage, delay, ratio, haste, icon_id, flags, source_primary, last_imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    1001,
                    "Pearl Earring",
                    "pearl earring",
                    "armor",
                    "2",
                    "ALL",
                    "ALL",
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
                    "STARTER,NO_TRADE_IMPORT",
                    "inventory_dump",
                    "2026-06-16 10:00:00",
                ),
                (
                    1002,
                    "Golden Earring",
                    "golden earring",
                    "armor",
                    "16",
                    "ALL",
                    "ALL",
                    2,
                    20,
                    5,
                    0,
                    1,
                    2,
                    3,
                    4,
                    5,
                    6,
                    7,
                    None,
                    None,
                    None,
                    None,
                    501,
                    "MAGIC",
                    "lucy",
                    "2026-06-16 10:00:00",
                ),
                (
                    2001,
                    "Coral Crescent",
                    "coral crescent",
                    "weapon",
                    "8192",
                    "WAR PAL RNG SHD MNK BRD ROG",
                    "ALL",
                    0,
                    0,
                    0,
                    0,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    12,
                    30,
                    0.4,
                    0,
                    601,
                    "MAGIC",
                    "lucy",
                    "2026-06-16 10:00:00",
                ),
                (
                    3001,
                    "Raw Hide",
                    "raw hide",
                    "misc",
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
                    "inventory_dump",
                    "2026-06-16 10:00:00",
                ),
                (
                    8001,
                    "Equipped Augment",
                    "equipped augment",
                    "augment",
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
                    "inventory_dump",
                    "2026-06-16 10:00:00",
                ),
                (
                    9001,
                    "Training Dagger",
                    "training dagger",
                    "weapon",
                    "8192",
                    "ALL",
                    "ALL",
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
                    "STARTER,NO_TRADE_IMPORT",
                    "inventory_dump",
                    "2026-06-16 10:00:00",
                ),
            ],
        )
        connection.execute(
            """
            INSERT INTO characters (character_name, character_class, level, server, notes, created_at, updated_at)
            VALUES ('Dreadnought', 'SHD', 60, 'frostreaver', 'tank', '2026-06-14 10:00:00', '2026-06-16 12:00:00')
            """
        )
        connection.executemany(
            """
            INSERT INTO inventory_imports (
                inventory_import_id, character_name, server, source_file, source_hash, source_size_bytes,
                parser_version, rows_seen, rows_imported, equipment_items_imported,
                inventory_items_imported, starter_items_seen, empty_rows_skipped, status, imported_at
            ) VALUES (?, 'Dreadnought', 'frostreaver', ?, ?, 1024, 'fixture_parser', ?, ?, ?, ?, ?, ?, 'completed', ?)
            """,
            [
                (1, "older.txt", "olderhash", 3, 3, 1, 2, 1, 0, "2026-06-15 12:00:00"),
                (2, "latest.txt", "latesthash", 8, 7, 2, 5, 2, 1, "2026-06-16 12:00:00"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO character_equipment (
                character_name, slot, slot_index, item_id, item_name, raw_item_name,
                normalized_item_name, inventory_import_id, server, raw_location, quantity,
                slots, is_starter_item
            ) VALUES ('Dreadnought', ?, ?, ?, ?, ?, ?, 2, 'frostreaver', ?, 1, ?, ?)
            """,
            [
                ("EAR", 1, 1001, "Pearl Earring", "Pearl Earring*", "pearl earring", "Ear", "2", 1),
                ("EAR", 2, 1002, "Golden Earring", "Golden Earring", "golden earring", "Ear", "16", 0),
            ],
        )
        connection.executemany(
            """
            INSERT INTO character_inventory_items (
                character_name, server, inventory_import_id, area, raw_location,
                parent_location, location_index, location_slot_index, item_id,
                item_name, raw_item_name, normalized_item_name, quantity, slots,
                is_container, is_starter_item, is_augment, augment_parent_location
            ) VALUES ('Dreadnought', 'frostreaver', 2, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "carried",
                    "General 1-Slot1",
                    "General 1",
                    1,
                    1,
                    2001,
                    "Coral Crescent",
                    "Coral Crescent",
                    "coral crescent",
                    2,
                    "8192",
                    0,
                    0,
                    0,
                    None,
                ),
                (
                    "carried",
                    "General 2-Slot1",
                    "General 2",
                    2,
                    1,
                    2001,
                    "Coral Crescent",
                    "Coral Crescent",
                    "coral crescent",
                    3,
                    "8192",
                    0,
                    0,
                    0,
                    None,
                ),
                (
                    "bank",
                    "Bank1",
                    None,
                    1,
                    None,
                    3001,
                    "Raw Hide",
                    "Raw Hide",
                    "raw hide",
                    6,
                    None,
                    0,
                    0,
                    0,
                    None,
                ),
                (
                    "shared_bank",
                    "Shared Bank1",
                    None,
                    1,
                    None,
                    9001,
                    "Training Dagger",
                    "Training Dagger*",
                    "training dagger",
                    1,
                    "8192",
                    0,
                    1,
                    0,
                    None,
                ),
                (
                    "equipped",
                    "Head-Aug1",
                    "Head",
                    None,
                    1,
                    8001,
                    "Equipped Augment",
                    "Equipped Augment",
                    "equipped augment",
                    1,
                    None,
                    0,
                    0,
                    1,
                    "Head",
                ),
            ],
        )
        connection.executemany(
            """
            INSERT INTO market_prices (
                item_id, server, median_pp, p25_pp, p75_pp, avg_pp, sample_size, confidence, last_refresh_at, source
            ) VALUES (?, 'frostreaver', ?, ?, ?, ?, ?, ?, '2026-06-16 12:30:00', 'fixture')
            """,
            [
                (1002, 1000, 900, 1200, 1100, 3, "medium"),
                (2001, 500, 450, 600, 525, 5, "high"),
            ],
        )
        connection.commit()


if __name__ == "__main__":
    unittest.main()

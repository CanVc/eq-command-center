from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from eqmarket.inventory_importer import (
    PARSER_VERSION,
    import_inventory_dump,
    infer_character_server_from_inventory_path,
    parse_inventory_dump,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "inventory"
DREADNOUGHT_FIXTURE = FIXTURE_DIR / "Dreadnought_frostreaver-Inventory.txt"
NOSEBLEED_FIXTURE = FIXTURE_DIR / "Nosebleed_frostreaver-Inventory.txt"


class InventoryDumpParserTests(unittest.TestCase):
    def test_infers_character_and_server_from_inventory_filename(self) -> None:
        inferred = infer_character_server_from_inventory_path(DREADNOUGHT_FIXTURE)

        self.assertEqual(inferred, ("Dreadnought", "frostreaver"))

    def test_parser_skips_empty_rows_and_marks_starter_and_augments(self) -> None:
        parsed = parse_inventory_dump(DREADNOUGHT_FIXTURE)

        self.assertEqual(parsed.rows_seen, 17)
        self.assertEqual(parsed.empty_rows_skipped, 1)
        self.assertEqual(parsed.starter_items_seen, 2)
        self.assertEqual(len(parsed.items), 16)

        starter = next(item for item in parsed.items if item.raw_item_name == "Training Dagger*")
        self.assertEqual(starter.item_name, "Training Dagger")
        self.assertEqual(starter.normalized_item_name, "training dagger")
        self.assertTrue(starter.is_starter_item)

        augment = next(item for item in parsed.items if item.raw_location == "Head-Aug1")
        self.assertTrue(augment.is_augment)
        self.assertEqual(augment.area, "equipped")
        self.assertEqual(augment.augment_parent_location, "Head")
        self.assertFalse(augment.is_equipment)

    def test_parser_ignores_trailing_keyring_section_header(self) -> None:
        dump = (
            "Location\tName\tID\tCount\tSlots\n"
            "Head\tKylong War Helm\t3213\t1\t6\n"
            "\n"
            "KeyRing\tName\tID\t\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            dump_path = Path(temp_dir) / "Amphetamin_frostreaver-Inventory.txt"
            dump_path.write_text(dump, encoding="utf-8")

            parsed = parse_inventory_dump(dump_path)

        self.assertEqual(parsed.rows_seen, 1)
        self.assertEqual(len(parsed.items), 1)
        self.assertEqual(parsed.items[0].item_name, "Kylong War Helm")


class InventoryImportTests(unittest.TestCase):
    def test_empty_dump_imports_without_current_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"

            stats = import_inventory_dump(db_path, NOSEBLEED_FIXTURE)

            self.assertEqual(stats.character_name, "Nosebleed")
            self.assertEqual(stats.server, "frostreaver")
            self.assertEqual(stats.rows_seen, 29)
            self.assertEqual(stats.rows_imported, 0)
            self.assertEqual(stats.empty_rows_skipped, 29)
            self.assertEqual(stats.equipment_items_imported, 0)
            self.assertEqual(stats.inventory_items_imported, 0)
            self.assertEqual(len(stats.source_hash), 64)

            with closing(sqlite3.connect(db_path)) as connection:
                character = connection.execute(
                    "SELECT character_name, character_class, server FROM characters WHERE character_name = 'Nosebleed'"
                ).fetchone()
                import_row = connection.execute(
                    """
                    SELECT character_name, server, source_hash, parser_version, rows_seen, rows_imported,
                           empty_rows_skipped, equipment_items_imported, inventory_items_imported
                    FROM inventory_imports
                    """
                ).fetchone()
                equipment_count = connection.execute("SELECT count(*) FROM character_equipment").fetchone()[0]
                inventory_count = connection.execute("SELECT count(*) FROM character_inventory_items").fetchone()[0]

            self.assertEqual(character, ("Nosebleed", "UNKNOWN", "frostreaver"))
            self.assertEqual(import_row[0:2], ("Nosebleed", "frostreaver"))
            self.assertEqual(len(import_row[2]), 64)
            self.assertEqual(import_row[3], PARSER_VERSION)
            self.assertEqual(import_row[4:], (29, 0, 29, 0, 0))
            self.assertEqual(equipment_count, 0)
            self.assertEqual(inventory_count, 0)

    def test_non_empty_dump_imports_equipment_inventory_bank_shared_and_stubs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"

            stats = import_inventory_dump(db_path, DREADNOUGHT_FIXTURE)

            self.assertEqual(stats.rows_seen, 17)
            self.assertEqual(stats.rows_imported, 16)
            self.assertEqual(stats.empty_rows_skipped, 1)
            self.assertEqual(stats.starter_items_seen, 2)
            self.assertEqual(stats.equipment_items_imported, 8)
            self.assertEqual(stats.inventory_items_imported, 8)
            self.assertEqual(stats.item_stubs_upserted, 16)
            self.assertEqual(stats.pending_items_upserted, 14)

            with closing(sqlite3.connect(db_path)) as connection:
                connection.row_factory = sqlite3.Row
                equipment_counts = dict(
                    connection.execute(
                        "SELECT slot, count(*) AS count FROM character_equipment GROUP BY slot"
                    ).fetchall()
                )
                duplicate_slots = connection.execute(
                    """
                    SELECT slot, slot_index, item_id
                    FROM character_equipment
                    WHERE slot IN ('EAR', 'WRIST', 'FINGER')
                    ORDER BY slot, slot_index
                    """
                ).fetchall()
                starter_equipment = connection.execute(
                    """
                    SELECT item_name, raw_item_name, normalized_item_name, is_starter_item
                    FROM character_equipment
                    WHERE item_id = 1001
                    """
                ).fetchone()
                inventory_area_counts = dict(
                    connection.execute(
                        "SELECT area, count(*) AS count FROM character_inventory_items GROUP BY area"
                    ).fetchall()
                )
                starter_inventory = connection.execute(
                    """
                    SELECT item_name, raw_item_name, normalized_item_name, is_starter_item
                    FROM character_inventory_items
                    WHERE item_id = 9001
                    """
                ).fetchone()
                augment = connection.execute(
                    """
                    SELECT area, raw_location, is_augment, augment_parent_location, item_id
                    FROM character_inventory_items
                    WHERE raw_location = 'Head-Aug1'
                    """
                ).fetchone()
                item_stub = connection.execute(
                    "SELECT name, normalized_name, flags, source_primary, slot FROM items WHERE item_id = 9001"
                ).fetchone()
                pending_names = {
                    row[0]
                    for row in connection.execute("SELECT normalized_name FROM pending_items").fetchall()
                }
                violations = connection.execute("PRAGMA foreign_key_check").fetchall()

            self.assertEqual(equipment_counts, {"EAR": 2, "FINGER": 2, "HEAD": 1, "PRIMARY": 1, "WRIST": 2})
            self.assertEqual(
                [(row["slot"], row["slot_index"], row["item_id"]) for row in duplicate_slots],
                [
                    ("EAR", 1, 1001),
                    ("EAR", 2, 1002),
                    ("FINGER", 1, 1005),
                    ("FINGER", 2, 1006),
                    ("WRIST", 1, 1003),
                    ("WRIST", 2, 1004),
                ],
            )
            self.assertEqual(tuple(starter_equipment), ("Pearl Earring", "Pearl Earring*", "pearl earring", 1))
            self.assertEqual(inventory_area_counts, {"bank": 2, "carried": 3, "equipped": 1, "shared_bank": 2})
            self.assertEqual(tuple(starter_inventory), ("Training Dagger", "Training Dagger*", "training dagger", 1))
            self.assertEqual(tuple(augment), ("equipped", "Head-Aug1", 1, "Head", 8001))
            self.assertEqual(item_stub[0:2], ("Training Dagger", "training dagger"))
            self.assertIn("STARTER", item_stub[2])
            self.assertEqual(item_stub[3], "inventory_dump")
            self.assertEqual(item_stub[4], "8192")
            self.assertNotIn("training dagger", pending_names)
            self.assertNotIn("pearl earring", pending_names)
            self.assertIn("coral crescent", pending_names)
            self.assertEqual(violations, [])

    def test_repeated_import_replaces_current_state_and_keeps_import_history(self) -> None:
        replacement_dump = (
            "Location\tName\tID\tCount\tSlots\n"
            "Head\tReplacement Helm\t6000\t1\t4\n"
            "General 1\tReplacement Satchel\t6001\t1\t10\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "eqmarket.sqlite"
            replacement_path = temp_path / "Dreadnought_frostreaver-Inventory.txt"

            import_inventory_dump(db_path, DREADNOUGHT_FIXTURE)
            replacement_path.write_text(replacement_dump, encoding="utf-8")
            replacement_stats = import_inventory_dump(db_path, replacement_path)

            with closing(sqlite3.connect(db_path)) as connection:
                import_count = connection.execute("SELECT count(*) FROM inventory_imports").fetchone()[0]
                current_equipment = connection.execute(
                    "SELECT slot, slot_index, item_id, item_name FROM character_equipment ORDER BY slot"
                ).fetchall()
                current_inventory = connection.execute(
                    "SELECT area, item_id, item_name FROM character_inventory_items ORDER BY item_id"
                ).fetchall()
                old_coral_count = connection.execute(
                    "SELECT count(*) FROM character_inventory_items WHERE item_id = 25817"
                ).fetchone()[0]

            self.assertEqual(import_count, 2)
            self.assertNotEqual(replacement_stats.source_hash, "")
            self.assertEqual(current_equipment, [("HEAD", 1, 6000, "Replacement Helm")])
            self.assertEqual(current_inventory, [("carried", 6001, "Replacement Satchel")])
            self.assertEqual(old_coral_count, 0)


if __name__ == "__main__":
    unittest.main()

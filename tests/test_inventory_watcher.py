from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from eqmarket.db import init_db
from eqmarket.inventory_watcher import InventoryWatcher, resolve_inventory_directory
from eqmarket.local_settings import set_configured_log_path


class InventoryWatcherTests(unittest.TestCase):
    def test_resolves_inventory_directory_from_configured_eq_log_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "eqmarket.sqlite"
            eq_dir = temp_path / "EverQuest"
            log_dir = eq_dir / "Logs"
            log_dir.mkdir(parents=True)
            log_path = log_dir / "eqlog_Dreadbank_frostreaver.txt"
            log_path.write_text("", encoding="utf-8")
            init_db(db_path)
            set_configured_log_path(db_path, str(log_path))

            self.assertEqual(resolve_inventory_directory(db_path), eq_dir.resolve())

    def test_poll_imports_latest_inventory_dump_from_eq_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "eqmarket.sqlite"
            eq_dir = temp_path / "EverQuest"
            log_dir = eq_dir / "Logs"
            log_dir.mkdir(parents=True)
            log_path = log_dir / "eqlog_Dreadbank_frostreaver.txt"
            inventory_path = eq_dir / "Dreadbank_frostreaver-Inventory.txt"
            log_path.write_text("", encoding="utf-8")
            _write_inventory_dump(inventory_path, carried_item="Silk Swatch", carried_item_id=1001)
            init_db(db_path)
            set_configured_log_path(db_path, str(log_path))
            watcher = InventoryWatcher(db_path)

            watcher.poll_once()
            status = watcher.status()

            with closing(sqlite3.connect(db_path)) as connection:
                import_row = connection.execute(
                    """
                    SELECT character_name, server, rows_imported, equipment_items_imported, inventory_items_imported
                    FROM inventory_imports
                    """
                ).fetchone()
                inventory_row = connection.execute(
                    "SELECT character_name, item_name FROM character_inventory_items"
                ).fetchone()

            self.assertEqual(status["inventory_directory"], str(eq_dir.resolve()))
            self.assertEqual(status["files_seen"], 1)
            self.assertEqual(status["files_imported"], 1)
            self.assertEqual(status["files_skipped"], 0)
            self.assertEqual(status["latest_import_character"], "Dreadbank")
            self.assertIsNone(status["error"])
            self.assertEqual(tuple(import_row), ("Dreadbank", "frostreaver", 2, 1, 1))
            self.assertEqual(tuple(inventory_row), ("Dreadbank", "Silk Swatch"))

    def test_poll_skips_unchanged_dump_then_imports_when_hash_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "eqmarket.sqlite"
            eq_dir = temp_path / "EverQuest"
            log_dir = eq_dir / "Logs"
            log_dir.mkdir(parents=True)
            log_path = log_dir / "eqlog_Dreadbank_frostreaver.txt"
            inventory_path = eq_dir / "Dreadbank_frostreaver-Inventory.txt"
            log_path.write_text("", encoding="utf-8")
            _write_inventory_dump(inventory_path, carried_item="Silk Swatch", carried_item_id=1001)
            init_db(db_path)
            set_configured_log_path(db_path, str(log_path))
            watcher = InventoryWatcher(db_path)

            watcher.poll_once()
            watcher.poll_once()
            skipped_status = watcher.status()
            _write_inventory_dump(inventory_path, carried_item="Spider Silk", carried_item_id=1002)
            watcher.poll_once()
            imported_status = watcher.status()

            with closing(sqlite3.connect(db_path)) as connection:
                import_count = connection.execute("SELECT count(*) FROM inventory_imports").fetchone()[0]
                current_inventory = connection.execute(
                    "SELECT item_name FROM character_inventory_items ORDER BY inventory_item_id"
                ).fetchall()

            self.assertEqual(skipped_status["files_imported"], 0)
            self.assertEqual(skipped_status["files_skipped"], 1)
            self.assertEqual(imported_status["files_imported"], 1)
            self.assertEqual(import_count, 2)
            self.assertEqual([row[0] for row in current_inventory], ["Spider Silk"])


def _write_inventory_dump(path: Path, *, carried_item: str, carried_item_id: int) -> None:
    path.write_text(
        "\n".join(
            [
                "Location\tName\tID\tCount\tSlots",
                "Primary\tPractice Sword\t9001\t1\t8192",
                f"General 1\t{carried_item}\t{carried_item_id}\t1\t0",
                "",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()

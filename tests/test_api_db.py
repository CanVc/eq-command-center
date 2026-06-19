from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from eqmarket.api.db import connect_readonly
from eqmarket.db import SCHEMA_PATH, init_db


class ApiDbTests(unittest.TestCase):
    def test_readonly_connection_uses_row_factory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute("CREATE TABLE sample (name TEXT NOT NULL)")
                connection.execute("INSERT INTO sample (name) VALUES ('krono')")
                connection.commit()

            with closing(connect_readonly(db_path)) as connection:
                row = connection.execute("SELECT name FROM sample").fetchone()

                self.assertEqual(row["name"], "krono")
                with self.assertRaises(sqlite3.OperationalError):
                    connection.execute("INSERT INTO sample (name) VALUES ('platinum')")

    def test_init_db_adds_inventory_columns_to_legacy_character_equipment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            legacy_schema = _legacy_schema_without_character_equipment_inventory_columns()
            with closing(sqlite3.connect(db_path)) as connection:
                connection.executescript(legacy_schema)
                connection.execute(
                    "INSERT INTO characters (character_name, character_class) VALUES ('Dreadnought', 'SHD')"
                )
                connection.execute(
                    "INSERT INTO items (item_id, name, normalized_name) VALUES (5732, 'Nathsar Helm', 'nathsar helm')"
                )
                connection.execute(
                    """
                    INSERT INTO character_equipment (character_name, slot, slot_index, item_id, item_name)
                    VALUES ('Dreadnought', 'HEAD', 1, 5732, 'Nathsar Helm')
                    """
                )
                connection.commit()

            init_db(db_path)

            with closing(sqlite3.connect(db_path)) as connection:
                columns = {row[1] for row in connection.execute("PRAGMA table_info('character_equipment')")}
                row = connection.execute(
                    """
                    SELECT quantity, is_starter_item, is_augment, raw_item_name, inventory_import_id
                    FROM character_equipment
                    WHERE character_name = 'Dreadnought' AND slot = 'HEAD'
                    """
                ).fetchone()
                import_index_exists = connection.execute(
                    """
                    SELECT 1
                    FROM sqlite_master
                    WHERE type = 'index' AND name = 'idx_character_equipment_import_id'
                    """
                ).fetchone()

            self.assertTrue(
                {
                    "raw_item_name",
                    "normalized_item_name",
                    "inventory_import_id",
                    "server",
                    "raw_location",
                    "quantity",
                    "slots",
                    "is_starter_item",
                    "is_augment",
                    "augment_parent_location",
                }.issubset(columns)
            )
            self.assertEqual(row, (1, 0, 0, None, None))
            self.assertIsNotNone(import_index_exists)


def _legacy_schema_without_character_equipment_inventory_columns() -> str:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    schema = schema.replace(
        """    raw_item_name TEXT,
    normalized_item_name TEXT,

    inventory_import_id INTEGER,
    server TEXT,
    raw_location TEXT,
    quantity INTEGER NOT NULL DEFAULT 1,
    slots TEXT,
    is_starter_item INTEGER NOT NULL DEFAULT 0,
    is_augment INTEGER NOT NULL DEFAULT 0,
    augment_parent_location TEXT,

""",
        "",
    )
    schema = schema.replace(
        "    FOREIGN KEY (inventory_import_id) REFERENCES inventory_imports(inventory_import_id) ON DELETE SET NULL,\n",
        "",
    )
    schema = schema.replace(
        """CREATE INDEX IF NOT EXISTS idx_character_equipment_import_id
    ON character_equipment(inventory_import_id);

""",
        "",
    )
    return schema

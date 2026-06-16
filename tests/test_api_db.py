from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from eqmarket.api.db import connect_readonly


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

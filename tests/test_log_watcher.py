from __future__ import annotations

from contextlib import closing
import gc
import sqlite3
import tempfile
import unittest
from pathlib import Path

from eqmarket.db import init_db
from eqmarket.local_settings import set_configured_log_path
from eqmarket.log_watcher import LogWatcher, infer_server_from_log_path


class LogWatcherTests(unittest.TestCase):
    def test_infers_server_from_eq_log_filename(self) -> None:
        self.assertEqual(infer_server_from_log_path("eqlog_Dreadbank_frostreaver.txt"), "frostreaver")
        self.assertEqual(infer_server_from_log_path("C:/Logs/eqlog_Name_With_Underscores_mischief.txt"), "mischief")
        self.assertIsNone(infer_server_from_log_path("auction.log"))

    def test_poll_starts_new_log_at_end_then_imports_appended_sales(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "eqmarket.sqlite"
            log_path = temp_path / "eqlog_Dreadbank_frostreaver.txt"
            init_db(db_path)
            log_path.write_text(
                "[Wed Jun 17 20:00:00 2026] Oldseller auctions, 'WTS Old Item 1k'\n",
                encoding="utf-8",
            )
            set_configured_log_path(db_path, str(log_path))
            watcher = LogWatcher(db_path)

            watcher.poll_once()
            with closing(sqlite3.connect(db_path)) as connection:
                initial_count = connection.execute("SELECT count(*) FROM market_listings").fetchone()[0]
                initial_position = connection.execute("SELECT last_position FROM log_import_state").fetchone()[0]

            with log_path.open("a", encoding="utf-8") as handle:
                handle.write("[Wed Jun 17 20:01:00 2026] Newseller auctions, 'WTS New Item 2k'\n")

            watcher.poll_once()
            status = watcher.status()
            with closing(sqlite3.connect(db_path)) as connection:
                rows = connection.execute(
                    "SELECT seller, item_name, price_pp, source FROM market_listings ORDER BY listing_id"
                ).fetchall()

            self.assertEqual(initial_count, 0)
            self.assertGreater(initial_position, 0)
            self.assertEqual(rows, [("Newseller", "New Item", 2000, "eq_log")])
            self.assertEqual(status["latest_sale_at"], "2026-06-17 20:01:00")
            self.assertIsNone(status["error"])
            watcher.stop()
            del watcher
            gc.collect()


if __name__ == "__main__":
    unittest.main()

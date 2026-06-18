from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from eqmarket.db import init_db
from eqmarket.price_repair import repair_listing_prices, repair_listing_raw_lines


class ListingPriceRepairTests(unittest.TestCase):
    def test_repair_listing_prices_updates_thousands_separator_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            bad_id, good_id, krono_id = _seed_price_repair_fixture(db_path)

            stats = repair_listing_prices(db_path, server="frostreaver")

            self.assertEqual(stats.listings_seen, 3)
            self.assertEqual(stats.reparsed_prices, 2)
            self.assertEqual(stats.updated, 1)

            rows = _listing_prices(db_path)
            self.assertEqual(rows[bad_id], (2000.0, "pp", 2000))
            self.assertEqual(rows[good_id], (2000.0, "pp", 2000))
            self.assertEqual(rows[krono_id], (1.0, "krono", 17000))

    def test_repair_listing_raw_lines_discards_stale_price_assignments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            raw_line = _seed_raw_line_repair_fixture(db_path)

            stats = repair_listing_raw_lines(db_path, server="frostreaver")

            self.assertEqual(stats.raw_lines_seen, 1)
            self.assertEqual(stats.raw_lines_reparsed, 1)
            self.assertEqual(stats.listings_seen, 4)
            self.assertEqual(stats.listings_matched, 2)
            self.assertEqual(stats.listings_inserted, 2)
            self.assertEqual(stats.listings_discarded, 2)

            rows = _raw_line_listing_rows(db_path, raw_line)
            self.assertEqual(
                rows,
                [
                    ("Yakatizma's Shield of Crafting", "1kr", "parsed", "discarded", "parser_reparse_mismatch"),
                    ("War Bow of Rallos Zek", "1kr", "parsed", "discarded", "parser_reparse_mismatch"),
                    ("Frostreaver's Velium Crown", "1kr", "parsed", None, None),
                    ("Dragons Tear Earring", "4kr", "parsed", None, None),
                    ("Yakatizma's Shield of Crafting", None, "no_price", None, None),
                    ("War Bow of Rallos Zek", None, "no_price", None, None),
                ],
            )


def _seed_price_repair_fixture(db_path: Path) -> tuple[int, int, int]:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        ids: list[int] = []
        for price_raw, price_amount, price_currency, price_pp in [
            ("2,000", 2, "pp", 2),
            ("2,000", 2000, "pp", 2000),
            ("1kr", 1, "krono", 17000),
        ]:
            cursor = connection.execute(
                """
                INSERT INTO market_listings (
                    server, timestamp, seller, item_name, normalized_item_name,
                    price_raw, price_amount, price_currency, price_pp, source, confidence
                ) VALUES ('frostreaver', '2026-06-18 12:00:00', 'Seller', 'Item', 'item', ?, ?, ?, ?, 'eq_log', 'parsed')
                """,
                (price_raw, price_amount, price_currency, price_pp),
            )
            ids.append(int(cursor.lastrowid))
        connection.commit()
    return ids[0], ids[1], ids[2]


def _seed_raw_line_repair_fixture(db_path: Path) -> str:
    raw_line = (
        "[Thu Jun 18 11:52:07 2026] Krtowin auctions, 'WTS Yakatizma's Shield of Crafting , "
        "War Bow of Rallos Zek , Frostreaver's Velium Crown 1kr, Dragons Tear Earring 4kr'"
    )
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        for item_name, normalized_name, price_raw, price_amount in [
            ("Yakatizma's Shield of Crafting", "yakatizma's shield of crafting", "1kr", 1),
            ("War Bow of Rallos Zek", "war bow of rallos zek", "1kr", 1),
            ("Frostreaver's Velium Crown", "frostreaver's velium crown", "1kr", 1),
            ("Dragons Tear Earring", "dragons tear earring", "4kr", 4),
        ]:
            connection.execute(
                """
                INSERT INTO market_listings (
                    server, timestamp, seller, item_name, normalized_item_name,
                    price_raw, price_amount, price_currency, price_pp, raw_line, source, confidence
                ) VALUES ('frostreaver', '2026-06-18 11:52:07', 'Krtowin', ?, ?, ?, ?, 'krono', NULL, ?, 'eq_log', 'parsed')
                """,
                (item_name, normalized_name, price_raw, price_amount, raw_line),
            )
        connection.commit()
    return raw_line


def _raw_line_listing_rows(db_path: Path, raw_line: str) -> list[tuple[str, str | None, str | None, str | None, str | None]]:
    with closing(sqlite3.connect(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT ml.item_name, ml.price_raw, ml.confidence, mlr.status, mlr.reason_code
            FROM market_listings ml
            LEFT JOIN market_listing_reviews mlr
                ON mlr.listing_id = ml.listing_id
            WHERE ml.raw_line = ?
            ORDER BY ml.listing_id
            """,
            (raw_line,),
        ).fetchall()
    return [(str(row[0]), row[1], row[2], row[3], row[4]) for row in rows]


def _listing_prices(db_path: Path) -> dict[int, tuple[float | None, str | None, int | None]]:
    with closing(sqlite3.connect(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT listing_id, price_amount, price_currency, price_pp
            FROM market_listings
            ORDER BY listing_id
            """
        ).fetchall()
    return {
        int(row[0]): (
            None if row[1] is None else float(row[1]),
            None if row[2] is None else str(row[2]),
            None if row[3] is None else int(row[3]),
        )
        for row in rows
    }


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eqmarket.db import init_db
from eqmarket.enrichment import enrich_pending_items
from eqmarket.inventory_importer import import_inventory_dump
from eqmarket.log_parser import normalize_item_name
from eqmarket.price_importer import import_tlp_prices, load_recent_listing_item_ids
from eqmarket.sources.lucy import LucyItem, LucySpell
from eqmarket.sources.tlp_auctions import CatalogItem, PricePoint


class InventoryEnrichmentPriceTargetTests(unittest.TestCase):
    def test_inventory_item_with_id_is_enriched_directly_from_lucy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "eqmarket.sqlite"
            dump_path = temp_path / "Story_frostreaver-Inventory.txt"
            dump_path.write_text(
                "Location\tName\tID\tCount\tSlots\n"
                "General 1\tID Known Sword\t501\t1\t8192\n",
                encoding="utf-8",
            )
            import_inventory_dump(db_path, dump_path)
            fake_lucy = _FakeLucyClient(
                raw_items={
                    501: {
                        "id": "501",
                        "name": "ID Known Sword",
                        "slots": "8192",
                        "magic": "1",
                        "nodrop": "1",
                        "norent": "1",
                        "ac": "7",
                        "hp": "25",
                    }
                }
            )

            with patch("eqmarket.enrichment.LucyClient", return_value=fake_lucy):
                stats = enrich_pending_items(db_path, limit=10)

            self.assertEqual(fake_lucy.fetch_item_calls, [501])
            self.assertEqual(fake_lucy.lookup_calls, [])
            self.assertEqual(stats.pending_seen, 1)
            self.assertEqual(stats.inventory_items_seen, 1)
            self.assertEqual(stats.items_imported, 1)

            with closing(sqlite3.connect(db_path)) as connection:
                item = connection.execute(
                    "SELECT source_primary, flags, ac, hp FROM items WHERE item_id = 501"
                ).fetchone()
                pending_status = connection.execute(
                    "SELECT status FROM pending_items WHERE normalized_name = 'id known sword'"
                ).fetchone()[0]

            self.assertEqual(item[0], "lucy")
            self.assertEqual(set(item[1].split(",")), {"MAGIC", "NO_DROP", "NO_RENT"})
            self.assertEqual(item[2:], (7, 25))
            self.assertEqual(pending_status, "resolved")

    def test_name_only_pending_item_keeps_lucy_lookup_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    "INSERT INTO pending_items (normalized_name, display_name) VALUES (?, ?)",
                    (normalize_item_name("Name Only Ring"), "Name Only Ring"),
                )
                connection.commit()

            fake_lucy = _FakeLucyClient(
                lookup_results={"Name Only Ring": [601]},
                raw_items={601: {"id": "601", "name": "Name Only Ring", "magic": "1"}},
            )

            with patch("eqmarket.enrichment.LucyClient", return_value=fake_lucy):
                stats = enrich_pending_items(db_path, limit=10)

            self.assertEqual(fake_lucy.lookup_calls, ["Name Only Ring"])
            self.assertEqual(fake_lucy.fetch_item_calls, [601])
            self.assertEqual(stats.inventory_items_seen, 0)
            self.assertEqual(stats.items_imported, 1)

            with closing(sqlite3.connect(db_path)) as connection:
                item = connection.execute(
                    "SELECT name, source_primary, flags FROM items WHERE item_id = 601"
                ).fetchone()
                pending_status = connection.execute(
                    "SELECT status FROM pending_items WHERE normalized_name = 'name only ring'"
                ).fetchone()[0]

            self.assertEqual(item, ("Name Only Ring", "lucy", "MAGIC"))
            self.assertEqual(pending_status, "resolved")

    def test_inventory_price_targets_skip_starters_containers_food_and_ignored_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "eqmarket.sqlite"
            dump_path = temp_path / "Seller_frostreaver-Inventory.txt"
            dump_path.write_text(
                "Location\tName\tID\tCount\tSlots\n"
                "General 1\tPrice Target Sword\t701\t1\t8192\n"
                "General 2\tTraining Dagger*\t702\t1\t8192\n"
                "General 3\tWater Flask\t703\t5\t0\n"
                "General 4\tLight Backpack\t704\t1\t10\n"
                "General 5\tIgnored Gem\t705\t1\t0\n",
                encoding="utf-8",
            )
            import_inventory_dump(db_path, dump_path)
            _ignore_item(db_path, 705, "Ignored Gem", "ignored gem")

            self.assertEqual(load_recent_listing_item_ids(db_path, "frostreaver", 10, max_age_hours=6), [701])

            fake_tlp = _FakeTlpAuctionsClient()
            with patch("eqmarket.price_importer.TlpAuctionsClient", return_value=fake_tlp):
                stats = import_tlp_prices(db_path, "frostreaver", history_days=None, concurrency=1)

            self.assertEqual(stats.inventory_items_targeted, 1)
            self.assertEqual(fake_tlp.history_calls, [701])
            self.assertEqual(stats.history_prices_upserted, 1)

            with closing(sqlite3.connect(db_path)) as connection:
                prices = connection.execute(
                    "SELECT item_id, median_pp, source FROM market_prices ORDER BY item_id"
                ).fetchall()

            self.assertEqual(prices, [(701, 1234, "tlp_auctions_history")])


class _FakeLucyClient:
    def __init__(
        self,
        *,
        lookup_results: dict[str, list[int]] | None = None,
        raw_items: dict[int, dict[str, str]] | None = None,
    ) -> None:
        self.lookup_results = lookup_results or {}
        self.raw_items = raw_items or {}
        self.lookup_calls: list[str] = []
        self.fetch_item_calls: list[int] = []

    def lookup_item_ids_by_exact_name(self, item_name: str) -> list[int]:
        self.lookup_calls.append(item_name)
        return list(self.lookup_results.get(item_name, []))

    def fetch_item_raw(self, item_id: int) -> LucyItem:
        self.fetch_item_calls.append(item_id)
        return LucyItem(item_id=item_id, fields=self.raw_items[item_id])

    def fetch_spell_raw(self, spell_id: int) -> LucySpell:
        raise AssertionError(f"unexpected spell fetch: {spell_id}")


class _FakeTlpAuctionsClient:
    def __init__(self) -> None:
        self.history_calls: list[int] = []

    def get_krono_price(self, server_name: str) -> None:
        return None

    def get_catalog(self, server_name: str) -> list[CatalogItem]:
        return [
            CatalogItem(item_id=701, name="Price Target Sword", price=1234),
            CatalogItem(item_id=702, name="Training Dagger", price=10),
            CatalogItem(item_id=703, name="Water Flask", price=1),
            CatalogItem(item_id=704, name="Light Backpack", price=100),
            CatalogItem(item_id=705, name="Ignored Gem", price=500),
        ]

    def get_item_history(self, item_id: int, server_name: str) -> list[PricePoint]:
        self.history_calls.append(item_id)
        if item_id == 701:
            return [
                PricePoint(
                    datetime="2026-06-17T10:00:00Z",
                    plat_price=1234,
                    krono_price=0,
                    is_buy=False,
                    auctioneer="Seller",
                )
            ]
        return []


def _ignore_item(db_path: Path, item_id: int, item_name: str, normalized_name: str) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            """
            INSERT INTO item_preferences (
                server, preference_key_kind, preference_key, item_id,
                item_name, normalized_item_name, status
            ) VALUES ('frostreaver', 'item_id', ?, ?, ?, ?, 'ignored')
            """,
            (str(item_id), item_id, item_name, normalized_name),
        )
        connection.commit()


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from eqmarket.api.app import create_app
from eqmarket.db import init_db


class ApiInventorySellCandidatesTests(unittest.TestCase):
    def test_character_sell_candidates_group_prices_and_default_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_sell_candidate_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get(
                    "/api/characters/Alpha/sell-candidates",
                    params={"local_listing_max_age_days": 3650},
                )

            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertEqual(payload["scope"], "character")
            self.assertEqual(payload["character_name"], "Alpha")
            self.assertEqual(payload["server"], "frostreaver")
            self.assertEqual(payload["item_count"], 9)
            self.assertEqual(payload["sellable_total_value_pp"], 3500)

            sellable_by_id = _items_by_id(payload["categories"]["sellable"])
            self.assertEqual(set(sellable_by_id), {101, 106, 107, 108})

            sell_gem = sellable_by_id[101]
            self.assertEqual(sell_gem["quantity"], 5)
            self.assertEqual(sell_gem["area_quantities"], {"carried": 2, "bank": 3})
            self.assertEqual(sell_gem["estimated_unit_price_pp"], 100)
            self.assertEqual(sell_gem["estimated_total_pp"], 500)
            self.assertEqual(sell_gem["price_source"], "fixture")
            self.assertEqual(sell_gem["confidence"], "medium")

            override_orb = sellable_by_id[106]
            self.assertEqual(override_orb["estimated_unit_price_pp"], 2000)
            self.assertEqual(override_orb["price_source"], "manual_override")
            self.assertEqual(override_orb["confidence"], "manual")

            listing_widget = sellable_by_id[107]
            self.assertEqual(listing_widget["estimated_unit_price_pp"], 300)
            self.assertEqual(listing_widget["price_source"], "recent_local_listings")
            self.assertEqual(listing_widget["confidence"], "low")

            self.assertEqual([item["item_id"] for item in payload["categories"]["no_drop"]], [102])
            self.assertTrue(payload["categories"]["no_drop"][0]["is_no_drop"])

            self.assertEqual([item["item_id"] for item in payload["categories"]["unpriced"]], [105])
            self.assertIsNone(payload["categories"]["unpriced"][0]["estimated_unit_price_pp"])

            excluded_by_id = _items_by_id(payload["categories"]["excluded"])
            self.assertEqual(set(excluded_by_id), {103, 104, 109})
            self.assertEqual(excluded_by_id[103]["default_exclusion_reasons"], ["starter"])
            self.assertEqual(excluded_by_id[104]["default_exclusion_reasons"], ["container", "consumable"])
            self.assertEqual(excluded_by_id[109]["default_exclusion_reasons"], ["consumable"])

            all_ids = {item["item_id"] for item in payload["items"]}
            self.assertNotIn(999, all_ids)

    def test_global_view_rolls_up_characters_and_manual_decisions_affect_buckets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_sell_candidate_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                initial = client.get(
                    "/api/inventory/sell-candidates",
                    params={"server": "frostreaver", "local_listing_max_age_days": 3650},
                )
                keep_response = client.put(
                    "/api/characters/Alpha/inventory/items/101/decision",
                    json={"status": "keep", "notes": "Hold for alt"},
                )
                ignore_response = client.put(
                    "/api/inventory/items/108/decision",
                    params={"server": "frostreaver"},
                    json={"status": "ignore", "notes": "Too noisy"},
                )
                after = client.get(
                    "/api/inventory/sell-candidates",
                    params={"server": "frostreaver", "local_listing_max_age_days": 3650},
                )

            self.assertEqual(initial.status_code, 200, initial.text)
            initial_rollups = _rollups_by_id(initial.json()["global_items"])
            self.assertEqual(initial_rollups[101]["quantity"], 9)
            self.assertEqual(initial_rollups[101]["estimated_total_pp"], 900)

            self.assertEqual(keep_response.status_code, 200, keep_response.text)
            self.assertEqual(keep_response.json()["scope"], "character")
            self.assertEqual(keep_response.json()["character_name"], "Alpha")
            self.assertEqual(keep_response.json()["status"], "keep")
            self.assertEqual(keep_response.json()["notes"], "Hold for alt")

            self.assertEqual(ignore_response.status_code, 200, ignore_response.text)
            self.assertEqual(ignore_response.json()["scope"], "global")
            self.assertIsNone(ignore_response.json()["character_name"])
            self.assertEqual(ignore_response.json()["status"], "ignore")

            self.assertEqual(after.status_code, 200, after.text)
            payload = after.json()

            keep_items = _items_by_id(payload["categories"]["keep"])
            self.assertIn(101, keep_items)
            self.assertEqual(keep_items[101]["character_name"], "Alpha")
            self.assertEqual(keep_items[101]["decision_status"], "keep")
            self.assertEqual(keep_items[101]["decision"]["scope"], "character")

            ignored_items = _items_by_id(payload["categories"]["ignored"])
            self.assertIn(108, ignored_items)
            self.assertEqual(ignored_items[108]["decision_status"], "ignore")
            self.assertEqual(ignored_items[108]["decision"]["scope"], "global")

            beta_sellable = [
                item
                for item in payload["categories"]["sellable"]
                if item["item_id"] == 101 and item["character_name"] == "Beta"
            ]
            self.assertEqual(len(beta_sellable), 1)
            self.assertEqual(beta_sellable[0]["quantity"], 4)

            rollups = _rollups_by_id(payload["global_items"])
            self.assertEqual(rollups[101]["quantity"], 9)
            self.assertEqual(rollups[101]["categories"], ["keep", "sellable"])


def _items_by_id(items: list[dict]) -> dict[int, dict]:
    return {int(item["item_id"]): item for item in items}


def _rollups_by_id(items: list[dict]) -> dict[int, dict]:
    return {int(item["item_id"]): item for item in items}


def _seed_sell_candidate_fixture(db_path: Path) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executemany(
            """
            INSERT INTO items (item_id, name, normalized_name, item_type, slot, flags, source_primary)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (101, "Sell Gem", "sell gem", "misc", None, "MAGIC", "lucy"),
                (102, "No Drop Sword", "no drop sword", "weapon", "8192", "MAGIC,NO_DROP", "lucy"),
                (103, "Training Dagger", "training dagger", "weapon", "8192", "STARTER,NO_TRADE_IMPORT", "inventory_dump"),
                (104, "Light Backpack", "light backpack", "container", None, None, "inventory_dump"),
                (105, "Unpriced Silk", "unpriced silk", "misc", None, None, "inventory_dump"),
                (106, "Override Orb", "override orb", "misc", None, "MAGIC", "lucy"),
                (107, "Listing Widget", "listing widget", "misc", None, "MAGIC", "lucy"),
                (108, "Ignore Dust", "ignore dust", "misc", None, "MAGIC", "lucy"),
                (109, "Water Flask", "water flask", "drink", None, None, "lucy"),
                (999, "Equipped Crown", "equipped crown", "armor", "4", "MAGIC", "lucy"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO characters (character_name, character_class, level, server)
            VALUES (?, 'CLR', 60, 'frostreaver')
            """,
            [("Alpha",), ("Beta",)],
        )
        connection.executemany(
            """
            INSERT INTO inventory_imports (
                inventory_import_id, character_name, server, source_file, source_hash,
                parser_version, rows_seen, rows_imported, inventory_items_imported
            ) VALUES (?, ?, 'frostreaver', ?, ?, 'fixture', 10, 10, 10)
            """,
            [
                (1, "Alpha", "alpha.txt", "alpha-hash"),
                (2, "Beta", "beta.txt", "beta-hash"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO character_inventory_items (
                character_name, server, inventory_import_id, area, raw_location,
                parent_location, location_index, location_slot_index, item_id,
                item_name, raw_item_name, normalized_item_name, quantity, slots,
                is_container, is_starter_item, is_augment
            ) VALUES (?, 'frostreaver', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            [
                ("Alpha", 1, "carried", "General 1-Slot1", "General 1", 1, 1, 101, "Sell Gem", "Sell Gem", "sell gem", 2, None, 0, 0),
                ("Alpha", 1, "bank", "Bank1", None, 1, None, 101, "Sell Gem", "Sell Gem", "sell gem", 3, None, 0, 0),
                ("Beta", 2, "carried", "General 1-Slot1", "General 1", 1, 1, 101, "Sell Gem", "Sell Gem", "sell gem", 4, None, 0, 0),
                ("Alpha", 1, "carried", "General 2-Slot1", "General 2", 2, 1, 102, "No Drop Sword", "No Drop Sword", "no drop sword", 1, "8192", 0, 0),
                ("Alpha", 1, "shared_bank", "Shared Bank1", None, 1, None, 103, "Training Dagger", "Training Dagger*", "training dagger", 1, "8192", 0, 1),
                ("Alpha", 1, "carried", "General 3", None, 3, None, 104, "Light Backpack", "Light Backpack", "light backpack", 1, None, 1, 0),
                ("Alpha", 1, "bank", "Bank2", None, 2, None, 105, "Unpriced Silk", "Unpriced Silk", "unpriced silk", 2, None, 0, 0),
                ("Alpha", 1, "carried", "General 4", None, 4, None, 106, "Override Orb", "Override Orb", "override orb", 1, None, 0, 0),
                ("Alpha", 1, "carried", "General 5", None, 5, None, 107, "Listing Widget", "Listing Widget", "listing widget", 1, None, 0, 0),
                ("Alpha", 1, "carried", "General 6", None, 6, None, 108, "Ignore Dust", "Ignore Dust", "ignore dust", 1, None, 0, 0),
                ("Alpha", 1, "carried", "General 7", None, 7, None, 109, "Water Flask", "Water Flask", "water flask", 5, None, 0, 0),
                ("Alpha", 1, "equipped", "Head", None, None, None, 999, "Equipped Crown", "Equipped Crown", "equipped crown", 1, "4", 0, 0),
            ],
        )
        connection.executemany(
            """
            INSERT INTO market_prices (
                item_id, server, median_pp, p25_pp, avg_pp, sample_size, confidence, last_refresh_at, source
            ) VALUES (?, 'frostreaver', ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 'fixture')
            """,
            [
                (101, 100, 80, 120, 5, "medium"),
                (102, 5000, 4500, 5200, 3, "low"),
                (103, 10, 5, 12, 2, "low"),
                (104, 25, 20, 30, 2, "low"),
                (106, 1000, 900, 1100, 10, "high"),
                (108, 700, 650, 800, 4, "low"),
                (109, 1, 1, 1, 20, "high"),
                (999, 100000, 90000, 110000, 5, "medium"),
            ],
        )
        connection.execute(
            """
            INSERT INTO market_prices_override (
                item_id, server, price_amount, price_currency, confidence, notes
            ) VALUES (106, 'frostreaver', 2000, 'pp', 'manual', 'fixture override')
            """
        )
        connection.execute(
            """
            INSERT INTO market_listings (
                server, timestamp, seller, item_name, normalized_item_name, item_id,
                price_raw, price_pp, source, confidence
            ) VALUES ('frostreaver', CURRENT_TIMESTAMP, 'WidgetSeller', 'Listing Widget',
                      'listing widget', 107, '300pp', 300, 'eq_log', 'parsed')
            """
        )
        connection.commit()


if __name__ == "__main__":
    unittest.main()

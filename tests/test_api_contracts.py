from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from eqmarket.api.app import create_app
from eqmarket.db import init_db
from eqmarket.log_importer import import_log_file


class ApiContractTests(unittest.TestCase):
    def test_core_endpoint_payload_shapes_stay_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_contract_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                health = client.get("/api/health")
                settings = client.get("/api/settings/status", params={"server": "frostreaver"})
                interface_tlp = client.get("/api/interface/tlp-errors", params={"server": "frostreaver"})
                interface_log = client.get("/api/interface/log-parse-issues", params={"server": "frostreaver"})
                dashboard = client.get("/api/dashboard/summary", params={"server": "frostreaver"})
                krono = client.get("/api/krono/latest", params={"server": "frostreaver"})
                deals = client.get("/api/deals", params={"server": "frostreaver"})
                listings = client.get("/api/listings/recent", params={"server": "frostreaver"})
                search = client.get("/api/items/search", params={"q": "contract"})
                item = client.get("/api/items/101")
                prices = client.get("/api/items/101/prices", params={"server": "frostreaver"})
                item_listings = client.get("/api/items/101/listings", params={"server": "frostreaver"})
                tooltip = client.get("/api/items/101/tooltip", params={"server": "frostreaver"})

            for response in [
                health,
                settings,
                interface_tlp,
                interface_log,
                dashboard,
                krono,
                deals,
                listings,
                search,
                item,
                prices,
                item_listings,
                tooltip,
            ]:
                self.assertEqual(response.status_code, 200, response.text)

            self.assertEqual(set(health.json()), {"status", "db_path"})
            self.assertEqual(
                set(settings.json()),
                {
                    "status",
                    "db_path",
                    "default_server",
                    "active_server",
                    "eq_log_path",
                    "eq_log_exists",
                    "eq_log_import_state",
                    "log_settings_error",
                },
            )
            self.assertTrue(
                {
                    "server",
                    "max_age_minutes",
                    "max_age_hours",
                    "stale_item_count",
                    "latest_tlp_import",
                    "active_errors",
                    "active_error_count",
                }.issubset(interface_tlp.json())
            )
            self.assertTrue({"server", "issues", "issue_count", "limit"}.issubset(interface_log.json()))
            self.assertTrue(
                {
                    "server",
                    "recent_window_hours",
                    "min_discount",
                    "listings_recent_count",
                    "deals_recent_count",
                    "krono_latest",
                    "top_seen_items",
                    "top_discounts",
                }.issubset(dashboard.json())
            )
            self.assertEqual(set(krono.json()), {"server", "price_pp", "source", "confidence", "last_refresh_at"})

            deal = deals.json()[0]
            self.assertTrue(
                {
                    "listing_id",
                    "timestamp",
                    "seller",
                    "item",
                    "item_id",
                    "item_name",
                    "price_raw",
                    "listing_price_pp",
                    "market_price_pp",
                    "market_price_source",
                    "discount_pct",
                    "potential_profit_pp",
                    "score",
                    "deal_score",
                    "sample_size",
                    "confidence",
                    "resolved",
                }.issubset(deal)
            )
            self.assertEqual(set(deal["item"]), {"item_id", "name"})

            listing = listings.json()[0]
            self.assertTrue(
                {
                    "listing_id",
                    "timestamp",
                    "seller",
                    "item",
                    "item_id",
                    "item_name",
                    "price_raw",
                    "price_pp",
                    "source",
                    "confidence",
                    "resolved",
                }.issubset(listing)
            )

            self.assertTrue({"item_id", "name", "icon_url", "slot", "classes", "flags"}.issubset(search.json()[0]))
            self.assertTrue({"item_id", "name", "icon_url", "stats", "combat", "levels", "effects"}.issubset(item.json()))
            self.assertTrue({"item_id", "server", "market_price_pp", "median_pp", "avg_pp", "sample_size"}.issubset(prices.json()))
            self.assertTrue({"listed_item_name", "resolved"}.issubset(item_listings.json()[0]))
            self.assertTrue({"item_id", "name", "icon_url", "market_price_pp", "last_seen_pp", "effects"}.issubset(tooltip.json()))

    def test_interface_log_parse_issues_returns_persisted_import_issues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "eqmarket.sqlite"
            log_path = temp_path / "eqlog_Test_frostreaver.txt"
            log_path.write_text(
                "[Tue Jun 16 10:00:00 2026] Seller auctions, 'WTS Unpriced Sword pst'\n",
                encoding="utf-8",
            )
            import_log_file(db_path, log_path, "frostreaver", incremental=False)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/interface/log-parse-issues", params={"server": "frostreaver"})

            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertEqual(payload["issue_count"], 1)
            self.assertEqual(payload["issues"][0]["reason_code"], "no_price")
            self.assertIn("Unpriced Sword", payload["issues"][0]["raw_line"])


def _seed_contract_fixture(db_path: Path) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            INSERT INTO items (item_id, name, normalized_name, slot, classes, flags)
            VALUES (101, 'Contract Sword', 'contract sword', 'PRIMARY', 'WAR PAL', 'MAGIC')
            """
        )
        connection.execute(
            """
            INSERT INTO market_prices (
                item_id, server, median_pp, p25_pp, avg_pp, sample_size, confidence, last_refresh_at, source
            ) VALUES (101, 'frostreaver', 1000, 800, 1100, 5, 'medium', '2026-06-16 10:00:00', 'fixture')
            """
        )
        connection.execute(
            """
            INSERT INTO market_listings (
                server, timestamp, seller, item_name, normalized_item_name, item_id,
                price_raw, price_pp, source, confidence
            ) VALUES ('frostreaver', '2026-06-16 11:00:00', 'ContractSeller', 'Contract Sword',
                      'contract sword', 101, '500pp', 500, 'eq_log', 'parsed')
            """
        )
        connection.execute(
            """
            INSERT INTO krono_prices (server, price_pp, source, confidence, last_refresh_at)
            VALUES ('frostreaver', 12000, 'fixture', 'high', '2026-06-16 10:00:00')
            """
        )
        connection.commit()


if __name__ == "__main__":
    unittest.main()

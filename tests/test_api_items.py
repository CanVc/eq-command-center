from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from eqmarket.api.app import create_app
from eqmarket.db import init_db
from eqmarket.sources.tlp_auctions import PricePoint


class ApiItemsTests(unittest.TestCase):
    def test_search_returns_matching_item_names_and_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_items_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/items/search", params={"q": "stave"})

            self.assertEqual(response.status_code, 200)
            payload = response.json()

            self.assertEqual(payload[0]["item_id"], 101)
            self.assertEqual(payload[0]["name"], "Stave of Shielding")
            self.assertIsNone(payload[0]["icon_url"])
            self.assertEqual(payload[0]["slot"], "PRIMARY")
            self.assertEqual(payload[0]["slot_mask"], 8192)
            self.assertEqual(payload[0]["slot_labels"], ["PRIMARY"])
            self.assertEqual(payload[0]["slot_display"], "PRIMARY")

    def test_item_preference_can_be_set_listed_and_cleared(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_items_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                wanted_response = client.put(
                    "/api/items/101/preference",
                    params={"server": "Frostreaver"},
                    json={"status": "wanted", "notes": "monk upgrade"},
                )
                detail_response = client.get("/api/items/101", params={"server": "frostreaver"})
                list_response = client.get("/api/items/preferences", params={"server": "frostreaver"})
                neutral_response = client.put(
                    "/api/items/101/preference",
                    params={"server": "frostreaver"},
                    json={"status": "neutral"},
                )
                cleared_response = client.get("/api/items/preferences", params={"server": "frostreaver"})

            self.assertEqual(wanted_response.status_code, 200, wanted_response.text)
            wanted_payload = wanted_response.json()
            self.assertEqual(wanted_payload["status"], "wanted")
            self.assertEqual(wanted_payload["preference_key_kind"], "item_id")
            self.assertEqual(wanted_payload["preference_key"], "101")
            self.assertEqual(wanted_payload["notes"], "monk upgrade")

            self.assertEqual(detail_response.status_code, 200, detail_response.text)
            self.assertEqual(detail_response.json()["item_preference"], "wanted")

            self.assertEqual(list_response.status_code, 200, list_response.text)
            self.assertEqual([preference["item_id"] for preference in list_response.json()], [101])

            self.assertEqual(neutral_response.status_code, 200, neutral_response.text)
            self.assertEqual(neutral_response.json()["status"], "neutral")
            self.assertEqual(cleared_response.json(), [])

    def test_item_detail_returns_stats_and_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_items_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/items/101")

            self.assertEqual(response.status_code, 200)
            payload = response.json()

            self.assertEqual(payload["item_id"], 101)
            self.assertEqual(payload["name"], "Stave of Shielding")
            self.assertIsNone(payload["icon_url"])
            self.assertEqual(payload["slot"], "PRIMARY")
            self.assertEqual(payload["slot_mask"], 8192)
            self.assertEqual(payload["slot_labels"], ["PRIMARY"])
            self.assertEqual(payload["slot_display"], "PRIMARY")
            self.assertEqual(payload["stats"]["hp"], 55)
            self.assertEqual(payload["stats"]["str"], 4)
            self.assertEqual(payload["combat"]["damage"], 12)
            self.assertEqual(payload["combat"]["delay"], 30)
            self.assertEqual(payload["combat"]["ratio"], 0.4)
            self.assertEqual(payload["effects"][0]["spell"], {"spell_id": 1806, "name": "Fungal Regrowth", "spell_type": "Beneficial", "target_type": "Self", "skill": "Alteration"})
            self.assertEqual(payload["effects"][0]["description"], "Fungal Regrowth")

    def test_item_payloads_decode_multi_and_duplicate_slot_masks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            with closing(sqlite3.connect(db_path)) as connection:
                connection.executemany(
                    """
                    INSERT INTO items (item_id, name, normalized_name, slot)
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        (201, "Dual Wield Test Sword", "dual wield test sword", "24576"),
                        (202, "Paired Wrist Test Bracer", "paired wrist test bracer", "1536"),
                    ],
                )
                connection.commit()
            app = create_app(db_path)

            with TestClient(app) as client:
                detail_response = client.get("/api/items/201")
                search_response = client.get("/api/items/search", params={"q": "paired wrist"})

            self.assertEqual(detail_response.status_code, 200, detail_response.text)
            detail_payload = detail_response.json()
            self.assertEqual(detail_payload["slot"], "PRIMARY / SECONDARY")
            self.assertEqual(detail_payload["slot_mask"], 24576)
            self.assertEqual(detail_payload["slot_labels"], ["PRIMARY", "SECONDARY"])
            self.assertEqual(detail_payload["slot_display"], "PRIMARY / SECONDARY")

            self.assertEqual(search_response.status_code, 200, search_response.text)
            search_payload = search_response.json()[0]
            self.assertEqual(search_payload["slot"], "WRIST")
            self.assertEqual(search_payload["slot_mask"], 1536)
            self.assertEqual(search_payload["slot_labels"], ["WRIST"])
            self.assertEqual(search_payload["slot_display"], "WRIST")

    def test_prices_return_market_payload_with_reference_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_items_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/items/101/prices", params={"server": "Frostreaver"})

            self.assertEqual(response.status_code, 200)
            payload = response.json()

            self.assertEqual(payload["item_id"], 101)
            self.assertEqual(payload["server"], "frostreaver")
            self.assertEqual(payload["market_price_pp"], 10000)
            self.assertEqual(payload["market_price_source"], "avg_pp")
            self.assertEqual(payload["median_pp"], 0)
            self.assertEqual(payload["p25_pp"], 8000)
            self.assertEqual(payload["p75_pp"], 12000)
            self.assertEqual(payload["avg_pp"], 10000)
            self.assertEqual(payload["sample_size"], 3)
            self.assertEqual(payload["confidence"], "low")

    def test_item_listings_are_filtered_by_item_and_server(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            listing_ids = _seed_items_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/items/101/listings", params={"server": "frostreaver", "limit": 1})

            self.assertEqual(response.status_code, 200)
            payload = response.json()

            self.assertEqual([listing["listing_id"] for listing in payload], [listing_ids["latest_stave"]])
            self.assertEqual(payload[0]["item"], {"item_id": 101, "name": "Stave of Shielding"})
            self.assertEqual(payload[0]["listed_item_name"], "Stave of Shielding MQ")
            self.assertEqual(payload[0]["price_raw"], "42k")
            self.assertEqual(
                payload[0]["raw_line"],
                "[Tue Jun 16 10:00:00 2026] LatestSeller auctions, 'WTS Stave of Shielding MQ 42k'",
            )
            self.assertEqual(payload[0]["price_pp"], 42000)
            self.assertTrue(payload[0]["resolved"])

    def test_tlp_history_returns_full_sell_history_with_krono_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_items_fixture(db_path)
            _seed_krono_price(db_path)
            app = create_app(db_path)

            fake_points = [
                PricePoint(
                    datetime="2026-06-14T10:00:00Z",
                    plat_price=5000,
                    krono_price=0,
                    is_buy=False,
                    auctioneer="SellerOne",
                ),
                PricePoint(
                    datetime="2026-06-01T10:00:00Z",
                    plat_price=1000,
                    krono_price=2,
                    is_buy=False,
                    auctioneer="SellerTwo",
                ),
                PricePoint(
                    datetime="2026-06-16T10:00:00Z",
                    plat_price=2000,
                    krono_price=0,
                    is_buy=True,
                    auctioneer="BuyerOne",
                ),
            ]

            with patch("eqmarket.api.routes.items.TlpAuctionsClient") as client_class:
                client_class.return_value.get_item_history.return_value = fake_points
                with TestClient(app) as client:
                    response = client.get("/api/items/101/tlp-history", params={"server": "frostreaver"})

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.json(),
                [
                    {
                        "timestamp": "2026-06-01T10:00:00Z",
                        "price_pp": 33000,
                        "plat_price": 1000,
                        "krono_price": 2,
                        "krono_price_pp_used": 16000,
                        "seller": "SellerTwo",
                        "source": "tlp_auctions_history",
                    },
                    {
                        "timestamp": "2026-06-14T10:00:00Z",
                        "price_pp": 5000,
                        "plat_price": 5000,
                        "krono_price": 0,
                        "krono_price_pp_used": None,
                        "seller": "SellerOne",
                        "source": "tlp_auctions_history",
                    },
                ],
            )

    def test_tooltip_by_id_contains_key_stats_prices_and_last_seen(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_items_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/items/101/tooltip", params={"server": "frostreaver"})

            self.assertEqual(response.status_code, 200)
            payload = response.json()

            self.assertEqual(payload["item_id"], 101)
            self.assertEqual(payload["name"], "Stave of Shielding")
            self.assertIsNone(payload["icon_url"])
            self.assertEqual(payload["slot"], "PRIMARY")
            self.assertEqual(payload["slot_mask"], 8192)
            self.assertEqual(payload["slot_labels"], ["PRIMARY"])
            self.assertEqual(payload["slot_display"], "PRIMARY")
            self.assertEqual(payload["classes"], "WAR PAL RNG SHD MNK BRD ROG")
            self.assertEqual(payload["ac"], 12)
            self.assertEqual(payload["hp"], 55)
            self.assertEqual(payload["mana"], 10)
            self.assertEqual(payload["damage"], 12)
            self.assertEqual(payload["delay"], 30)
            self.assertEqual(payload["ratio"], 0.4)
            self.assertEqual(payload["flags"], "MAGIC")
            self.assertEqual(payload["market_price_pp"], 10000)
            self.assertEqual(payload["market_price_source"], "avg_pp")
            self.assertEqual(payload["last_seen_pp"], 42000)
            self.assertEqual(payload["last_seen_at"], "2026-06-16 12:00:00")
            self.assertEqual(payload["effects"][0]["spell"]["name"], "Fungal Regrowth")

    def test_tooltip_fallback_by_name_uses_normalized_item_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            _seed_items_fixture(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get(
                    "/api/items/tooltip",
                    params={"name": "  STAVE   OF   SHIELDING  ", "server": "frostreaver"},
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["item_id"], 101)

    def test_absent_item_returns_clean_404(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                id_response = client.get("/api/items/999")
                name_response = client.get("/api/items/tooltip", params={"name": "Missing Item"})

            self.assertEqual(id_response.status_code, 404)
            self.assertEqual(id_response.json(), {"detail": "Item not found"})
            self.assertEqual(name_response.status_code, 404)
            self.assertEqual(name_response.json(), {"detail": "Item not found"})


def _seed_items_fixture(db_path: Path) -> dict[str, int]:
    listing_ids: dict[str, int] = {}

    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executemany(
            """
            INSERT INTO items (
                item_id, name, normalized_name, item_type, slot, classes, races,
                ac, hp, mana, endurance, hp_regen, mana_regen, endurance_regen,
                astr, asta, aagi, adex, awis, aint, acha,
                sv_magic, sv_fire, sv_cold, sv_poison, sv_disease,
                damage, delay, ratio, haste, required_level, recommended_level,
                icon_id, flags, source_primary, last_imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    101,
                    "Stave of Shielding",
                    "stave of shielding",
                    "weapon",
                    "8192",
                    "WAR PAL RNG SHD MNK BRD ROG",
                    "ALL",
                    12,
                    55,
                    10,
                    0,
                    1,
                    0,
                    0,
                    4,
                    5,
                    6,
                    7,
                    8,
                    9,
                    10,
                    11,
                    12,
                    13,
                    14,
                    15,
                    12,
                    30,
                    0.4,
                    0,
                    45,
                    50,
                    601,
                    "MAGIC",
                    "fixture",
                    "2026-06-16 09:00:00",
                ),
                (
                    102,
                    "Runed Crown",
                    "runed crown",
                    "armor",
                    "4",
                    "ALL",
                    "ALL",
                    20,
                    80,
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
                    None,
                    None,
                    None,
                    None,
                    "MAGIC",
                    "fixture",
                    "2026-06-16 09:00:00",
                ),
                (
                    103,
                    "Other Server Item",
                    "other server item",
                    "armor",
                    "131072",
                    "ALL",
                    "ALL",
                    1,
                    2,
                    3,
                    4,
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
                    None,
                    None,
                    None,
                    "fixture",
                    "2026-06-16 09:00:00",
                ),
            ],
        )
        connection.executemany(
            """
            INSERT INTO market_prices (
                item_id, server, median_pp, p25_pp, p75_pp, avg_pp, min_pp, max_pp,
                sample_size, confidence, last_refresh_at, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (101, "frostreaver", 0, 8000, 12000, 10000, 7000, 15000, 3, "low", "2026-06-16 09:30:00", "fixture"),
                (102, "frostreaver", 90000, 75000, 110000, 95000, 70000, 120000, 20, "high", "2026-06-16 09:30:00", "fixture"),
                (103, "other", 5000, 4000, 6000, 5500, 3500, 6500, 5, "medium", "2026-06-16 09:30:00", "fixture"),
            ],
        )
        connection.execute(
            """
            INSERT INTO spells (
                spell_id, name, normalized_name, spell_type, target_type, skill, source_server
            ) VALUES (1806, 'Fungal Regrowth', 'fungal regrowth', 'Beneficial', 'Self', 'Alteration', 'Live')
            """
        )
        connection.execute(
            """
            INSERT INTO item_effects (
                item_id, effect_slot, spell_id, trigger_type, effect_type_raw,
                cast_time_ms, effective_level
            ) VALUES (101, 0, 1806, 'worn', 1, 0, 0)
            """
        )

        listing_rows = [
            (
                "older_stave",
                "frostreaver",
                "2026-06-16 11:00:00",
                "OlderSeller",
                "Stave of Shielding",
                "stave of shielding",
                101,
                "50k",
                50000,
            ),
            (
                "latest_stave",
                "frostreaver",
                "2026-06-16 12:00:00",
                "LatestSeller",
                "Stave of Shielding MQ",
                "stave of shielding mq",
                101,
                "42k",
                42000,
            ),
            (
                "other_item",
                "frostreaver",
                "2026-06-16 13:00:00",
                "OtherSeller",
                "Runed Crown",
                "runed crown",
                102,
                "80k",
                80000,
            ),
            (
                "other_server",
                "other",
                "2026-06-16 14:00:00",
                "RemoteSeller",
                "Stave of Shielding",
                "stave of shielding",
                101,
                "1k",
                1000,
            ),
        ]

        for key, server, timestamp, seller, item_name, normalized_name, item_id, price_raw, price_pp in listing_rows:
            raw_line = f"[Tue Jun 16 10:00:00 2026] {seller} auctions, 'WTS {item_name} {price_raw}'"
            cursor = connection.execute(
                """
                INSERT INTO market_listings (
                    server, timestamp, seller, item_name, normalized_item_name, item_id,
                    price_raw, price_pp, raw_line, source, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'eq_log', 'parsed')
                """,
                (server, timestamp, seller, item_name, normalized_name, item_id, price_raw, price_pp, raw_line),
            )
            listing_ids[key] = int(cursor.lastrowid)

        connection.commit()

    return listing_ids


def _seed_krono_price(db_path: Path) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            """
            INSERT INTO krono_prices (server, price_pp, source, confidence, last_refresh_at)
            VALUES ('frostreaver', 16000, 'fixture', 'high', '2026-06-16 10:00:00')
            """
        )
        connection.commit()

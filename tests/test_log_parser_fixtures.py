from __future__ import annotations

import unittest
from pathlib import Path

from eqmarket.log_importer import parse_log_file
from eqmarket.log_parser import normalize_item_name, parse_auction_line, parse_sale_listings


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "logs"


class LogParserFixtureTests(unittest.TestCase):
    def test_auction_fixture_parses_realistic_sale_cases(self) -> None:
        listings = parse_log_file(FIXTURES_DIR / "auction_sample_01.txt")

        self.assertEqual(len(listings), 4)
        self.assertEqual(
            [(listing.seller, listing.item_name, listing.price_raw, listing.price_currency, listing.price_pp, listing.confidence) for listing in listings],
            [
                ("Nebblastin", "Stave of Shielding", "42k", "pp", 42000, "parsed"),
                ("Sellerone", "Spider Silk", "25pp", "pp", 25, "parsed"),
                ("Kronoman", "Fungi Covered Scale Tunic", "2 krono", "krono", None, "parsed"),
                ("Mystery", "Mystery Blade", None, None, None, "no_price"),
            ],
        )

    def test_auction_fixture_ignores_wtb_lines(self) -> None:
        listings = parse_log_file(FIXTURES_DIR / "auction_sample_01.txt")

        self.assertNotIn("Cloak of Flames", [listing.item_name for listing in listings])

    def test_price_after_separator_applies_only_to_nearest_item(self) -> None:
        auction = parse_auction_line(
            "[Thu Jun 18 11:38:58 2026] Cimed auctions, 'WTS Truesight Helmet , "
            "Staff of Elemental Mastery: Water 3kr, Shroud of Longevity , Mask of Venom 1kr'"
        )
        self.assertIsNotNone(auction)

        listings = parse_sale_listings(auction)

        self.assertEqual(
            [(listing.item_name, listing.price_raw, listing.price_currency, listing.price_pp, listing.confidence) for listing in listings],
            [
                ("Truesight Helmet", None, None, None, "no_price"),
                ("Staff of Elemental Mastery: Water", "3kr", "krono", None, "parsed"),
                ("Shroud of Longevity", None, None, None, "no_price"),
                ("Mask of Venom", "1kr", "krono", None, "parsed"),
            ],
        )

    def test_partial_price_list_keeps_unpriced_items_unpriced(self) -> None:
        auction = parse_auction_line(
            "[Thu Jun 18 11:52:07 2026] Krtowin auctions, 'WTS Yakatizma's Shield of Crafting , "
            "War Bow of Rallos Zek , Frostreaver's Velium Crown 1kr, Dragons Tear Earring 4kr'"
        )
        self.assertIsNotNone(auction)

        listings = parse_sale_listings(auction)

        self.assertEqual(
            [(listing.item_name, listing.price_raw, listing.price_currency, listing.price_pp, listing.confidence) for listing in listings],
            [
                ("Yakatizma's Shield of Crafting", None, None, None, "no_price"),
                ("War Bow of Rallos Zek", None, None, None, "no_price"),
                ("Frostreaver's Velium Crown", "1kr", "krono", None, "parsed"),
                ("Dragons Tear Earring", "4kr", "krono", None, "parsed"),
            ],
        )

    def test_each_price_still_applies_to_split_items(self) -> None:
        auction = parse_auction_line(
            "[Thu Jun 18 11:52:07 2026] Seller auctions, 'WTS Item One, Item Two 500pp each, Item Three'"
        )
        self.assertIsNotNone(auction)

        listings = parse_sale_listings(auction)

        self.assertEqual(
            [(listing.item_name, listing.price_raw, listing.price_pp, listing.confidence) for listing in listings],
            [
                ("Item One", "500pp", 500, "parsed"),
                ("Item Two", "500pp", 500, "parsed"),
                ("Item Three", None, None, "no_price"),
            ],
        )

    def test_platinum_price_supports_thousands_separators(self) -> None:
        for separator in (",", "."):
            with self.subTest(separator=separator):
                auction = parse_auction_line(
                    f"[Thu Jun 18 09:18:40 2026] Zanglo auctions, 'WTS Fungus Covered Scale Tunic 12{separator}000p "
                    "Woodsman's Staff 500p Sword of Pain 500p obo PST!'"
                )
                self.assertIsNotNone(auction)

                listings = parse_sale_listings(auction)

                self.assertEqual(listings[0].item_name, "Fungus Covered Scale Tunic")
                self.assertEqual(listings[0].price_raw, f"12{separator}000p")
                self.assertEqual(listings[0].price_amount, 12000)
                self.assertEqual(listings[0].price_pp, 12000)

    def test_k_price_with_thousands_separator_keeps_k_multiplier(self) -> None:
        auction = parse_auction_line("[Thu Jun 18 09:18:40 2026] Seller auctions, 'WTS Rare Sword 12,000k'")
        self.assertIsNotNone(auction)

        listings = parse_sale_listings(auction)

        self.assertEqual(listings[0].price_raw, "12,000k")
        self.assertEqual(listings[0].price_amount, 12000)
        self.assertEqual(listings[0].price_pp, 12_000_000)

    def test_normalize_item_name_collapses_case_spacing_and_backticks(self) -> None:
        self.assertEqual(normalize_item_name("  Hierophant`s   Cloak  "), "hierophant's cloak")


if __name__ == "__main__":
    unittest.main()

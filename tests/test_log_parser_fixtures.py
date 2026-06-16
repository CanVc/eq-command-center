from __future__ import annotations

import unittest
from pathlib import Path

from eqmarket.log_importer import parse_log_file
from eqmarket.log_parser import normalize_item_name


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

    def test_normalize_item_name_collapses_case_spacing_and_backticks(self) -> None:
        self.assertEqual(normalize_item_name("  Hierophant`s   Cloak  "), "hierophant's cloak")


if __name__ == "__main__":
    unittest.main()

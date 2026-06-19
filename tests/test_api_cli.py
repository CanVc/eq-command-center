from __future__ import annotations

import unittest

from eqmarket.__main__ import build_parser


class ApiCliTests(unittest.TestCase):
    def test_serve_api_defaults_to_loopback(self) -> None:
        args = build_parser().parse_args(["serve-api"])

        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 8000)

    def test_import_inventory_accepts_file_with_optional_character_server(self) -> None:
        args = build_parser().parse_args(["import-inventory", "--file", "Dreadnought_frostreaver-Inventory.txt"])

        self.assertEqual(args.file, "Dreadnought_frostreaver-Inventory.txt")
        self.assertIsNone(args.character)
        self.assertIsNone(args.server)

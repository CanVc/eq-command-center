from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from eqmarket.db import init_db
from eqmarket.enrichment import upsert_lucy_item
from eqmarket.slot_masks import decode_lucy_slot_mask


class LucySlotMaskTests(unittest.TestCase):
    def test_decodes_single_primary_slot(self) -> None:
        decoded = decode_lucy_slot_mask("8192")

        self.assertEqual(decoded.slot_mask, 8192)
        self.assertEqual(decoded.slot_labels, ("PRIMARY",))
        self.assertEqual(decoded.slot_display, "PRIMARY")
        self.assertEqual(decoded.unknown_bits, 0)

    def test_decodes_multi_slot_mask(self) -> None:
        decoded = decode_lucy_slot_mask(24576)

        self.assertEqual(decoded.slot_mask, 24576)
        self.assertEqual(decoded.slot_labels, ("PRIMARY", "SECONDARY"))
        self.assertEqual(decoded.slot_display, "PRIMARY / SECONDARY")

    def test_deduplicates_duplicate_physical_slots(self) -> None:
        for slot_mask, label in [(18, "EAR"), (1536, "WRIST"), (98304, "FINGER")]:
            with self.subTest(slot_mask=slot_mask):
                decoded = decode_lucy_slot_mask(slot_mask)

                self.assertEqual(decoded.slot_mask, slot_mask)
                self.assertEqual(decoded.slot_labels, (label,))
                self.assertEqual(decoded.slot_display, label)

    def test_decodes_exotic_mask_and_unknown_bits(self) -> None:
        decoded = decode_lucy_slot_mask(4 + 32 + 512 + 8_388_608)

        self.assertEqual(decoded.slot_mask, 8_389_156)
        self.assertEqual(decoded.slot_labels, ("HEAD", "NECK", "WRIST", "UNKNOWN(8388608)"))
        self.assertEqual(decoded.slot_display, "HEAD / NECK / WRIST / UNKNOWN(8388608)")
        self.assertEqual(decoded.unknown_bits, 8_388_608)

    def test_lucy_import_preserves_raw_slot_mask_in_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            with closing(sqlite3.connect(db_path)) as connection:
                upsert_lucy_item(
                    connection,
                    {
                        "id": "9001",
                        "name": "Two Hand Test Sword",
                        "slots": "24576",
                    },
                )
                connection.commit()

            with closing(sqlite3.connect(db_path)) as connection:
                stored_slot = connection.execute(
                    "SELECT slot FROM items WHERE item_id = 9001"
                ).fetchone()[0]

        self.assertEqual(stored_slot, "24576")


if __name__ == "__main__":
    unittest.main()

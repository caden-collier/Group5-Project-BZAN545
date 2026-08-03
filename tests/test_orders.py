from __future__ import annotations

import tempfile
import unittest
from io import StringIO
from pathlib import Path

from bzan545.orders import (
    NEW_PRODUCT_ID_COLUMNS,
    PRODUCT_ID_COLUMNS,
    PreservationError,
    inspect_orders,
    preserve_orders_bytes,
    sha256_bytes,
    validate_orders_bytes,
)


VALID_ROW = (
    "20260731-0001", "2026-07-31", "S005", "NP5047", "1", "58.07",
    "0", "ship_from_store", "N",
)


def make_csv(*rows: tuple[str, ...], columns=NEW_PRODUCT_ID_COLUMNS) -> bytes:
    lines = [",".join(columns), *(",".join(row) for row in rows)]
    return ("\n".join(lines) + "\n").encode()


class OrdersTests(unittest.TestCase):
    def test_accepts_old_and_new_product_schemas(self) -> None:
        new_facts = validate_orders_bytes(make_csv(VALID_ROW))
        old_row = (*VALID_ROW[:3], "P1047", *VALID_ROW[4:])
        old_facts = validate_orders_bytes(make_csv(old_row, columns=PRODUCT_ID_COLUMNS))
        self.assertEqual(new_facts.product_id_column, "new_product_id")
        self.assertEqual(old_facts.product_id_column, "product_id")

    def test_rejects_invalid_content(self) -> None:
        for data in (b"", b"<html>error</html>"):
            with self.assertRaises(PreservationError):
                validate_orders_bytes(data)
        with self.assertRaises(PreservationError):
            validate_orders_bytes(make_csv())

    def test_preservation_is_atomic_idempotent_and_hashed(self) -> None:
        data = make_csv(VALID_ROW)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            preserve_orders_bytes(data, raw_root=root)
            preserve_orders_bytes(data, raw_root=root)
            date_dir = root / "2026-07-31"
            self.assertEqual((date_dir / "orders.csv").read_bytes(), data)
            self.assertEqual(
                (date_dir / "orders.csv.sha256").read_text(),
                f"{sha256_bytes(data)}  orders.csv\n",
            )

    def test_inspection_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "orders.csv"
            path.write_bytes(make_csv(VALID_ROW))
            before = path.read_bytes()
            output = StringIO()
            facts = inspect_orders(path, output=output)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(facts.row_count, 1)
            self.assertIn("Order date: 2026-07-31", output.getvalue())


if __name__ == "__main__":
    unittest.main()

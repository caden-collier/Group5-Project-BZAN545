from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.preserve_daily_orders import (
    EXPECTED_COLUMNS,
    PRODUCT_ID_COLUMNS,
    PreservationError,
    preserve_orders_bytes,
    sha256_bytes,
    validate_orders_bytes,
)


VALID_ROW = (
    "20260729-0001",
    "2026-07-29",
    "S005",
    "NP5047",
    "1",
    "58.07",
    "0",
    "ship_from_store",
    "N",
)


def make_csv(
    *rows: tuple[str, ...],
    columns: tuple[str, ...] = EXPECTED_COLUMNS,
) -> bytes:
    lines = [",".join(columns), *(",".join(row) for row in rows)]
    return ("\n".join(lines) + "\n").encode("utf-8")


class ValidateOrdersTests(unittest.TestCase):
    def test_valid_csv_reports_facts(self) -> None:
        data = make_csv(VALID_ROW)
        facts = validate_orders_bytes(data)
        self.assertEqual(facts.order_date, "2026-07-29")
        self.assertEqual(facts.row_count, 1)
        self.assertEqual(facts.sha256, sha256_bytes(data))

    def test_accepts_the_earlier_product_id_schema(self) -> None:
        earlier_row = list(VALID_ROW)
        earlier_row[3] = "P1047"
        facts = validate_orders_bytes(
            make_csv(tuple(earlier_row), columns=PRODUCT_ID_COLUMNS)
        )
        self.assertEqual(facts.order_date, "2026-07-29")

    def test_rejects_empty_html_and_reordered_columns(self) -> None:
        with self.assertRaises(PreservationError):
            validate_orders_bytes(b"")
        with self.assertRaises(PreservationError):
            validate_orders_bytes(b"<!doctype html><title>Error</title>")
        reordered = (EXPECTED_COLUMNS[1], EXPECTED_COLUMNS[0], *EXPECTED_COLUMNS[2:])
        with self.assertRaises(PreservationError):
            validate_orders_bytes(make_csv(VALID_ROW, columns=reordered))

    def test_rejects_multiple_or_invalid_dates(self) -> None:
        second_row = list(VALID_ROW)
        second_row[0] = "20260730-0001"
        second_row[1] = "2026-07-30"
        with self.assertRaises(PreservationError):
            validate_orders_bytes(make_csv(VALID_ROW, tuple(second_row)))

        invalid_row = list(VALID_ROW)
        invalid_row[1] = "07/29/2026"
        with self.assertRaises(PreservationError):
            validate_orders_bytes(make_csv(tuple(invalid_row)))


class PreserveOrdersTests(unittest.TestCase):
    def test_preserves_bytes_and_checksum(self) -> None:
        data = make_csv(VALID_ROW)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            preserve_orders_bytes(data, raw_root=root)
            date_dir = root / "2026-07-29"
            self.assertEqual((date_dir / "orders.csv").read_bytes(), data)
            self.assertEqual(
                (date_dir / "orders.csv.sha256").read_text(encoding="utf-8"),
                f"{sha256_bytes(data)}  orders.csv\n",
            )

    def test_identical_repeat_is_a_no_op(self) -> None:
        data = make_csv(VALID_ROW)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            preserve_orders_bytes(data, raw_root=root)
            before = sorted(path.name for path in (root / "2026-07-29").iterdir())
            preserve_orders_bytes(data, raw_root=root)
            after = sorted(path.name for path in (root / "2026-07-29").iterdir())
            self.assertEqual(before, after)

    def test_different_existing_file_is_not_overwritten(self) -> None:
        original = make_csv(VALID_ROW)
        changed_row = list(VALID_ROW)
        changed_row[3] = "NP5999"
        changed = make_csv(tuple(changed_row))
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            preserve_orders_bytes(original, raw_root=root)
            with self.assertRaises(PreservationError):
                preserve_orders_bytes(changed, raw_root=root)
            self.assertEqual(
                (root / "2026-07-29" / "orders.csv").read_bytes(),
                original,
            )

    def test_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            preserve_orders_bytes(make_csv(VALID_ROW), raw_root=root, dry_run=True)
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

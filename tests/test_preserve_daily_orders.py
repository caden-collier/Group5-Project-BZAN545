from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.preserve_daily_orders import (
    EXPECTED_COLUMNS,
    PreservationError,
    preserve_orders_bytes,
    sha256_bytes,
    validate_orders_bytes,
)


def make_csv(*rows: tuple[str, ...], columns: tuple[str, ...] = EXPECTED_COLUMNS) -> bytes:
    lines = [",".join(columns), *(",".join(row) for row in rows)]
    return ("\n".join(lines) + "\n").encode("utf-8")


VALID_ROW = (
    "20260719-0001",
    "2026-07-19",
    "S001",
    "P1001",
    "2",
    "10.50",
    "0",
    "in_store",
    "Y",
)


class ValidateOrdersTests(unittest.TestCase):
    def test_valid_csv_reports_expected_facts(self) -> None:
        data = make_csv(VALID_ROW)
        facts = validate_orders_bytes(data)
        self.assertEqual(facts.order_date, "2026-07-19")
        self.assertEqual(facts.row_count, 1)
        self.assertEqual(facts.column_count, 9)
        self.assertEqual(facts.sha256, sha256_bytes(data))

    def test_rejects_empty_file(self) -> None:
        with self.assertRaisesRegex(PreservationError, "empty"):
            validate_orders_bytes(b"")

    def test_rejects_html(self) -> None:
        with self.assertRaisesRegex(PreservationError, "HTML"):
            validate_orders_bytes(b"<!doctype html><title>Error</title>")

    def test_rejects_unexpected_or_reordered_columns(self) -> None:
        reordered = (EXPECTED_COLUMNS[1], EXPECTED_COLUMNS[0], *EXPECTED_COLUMNS[2:])
        with self.assertRaisesRegex(PreservationError, "Unexpected columns"):
            validate_orders_bytes(make_csv(VALID_ROW, columns=reordered))

    def test_rejects_header_without_rows(self) -> None:
        with self.assertRaisesRegex(PreservationError, "no order rows"):
            validate_orders_bytes(make_csv())

    def test_rejects_multiple_dates(self) -> None:
        second_row = list(VALID_ROW)
        second_row[0] = "20260720-0001"
        second_row[1] = "2026-07-20"
        with self.assertRaisesRegex(PreservationError, "exactly one"):
            validate_orders_bytes(make_csv(VALID_ROW, tuple(second_row)))

    def test_rejects_invalid_date(self) -> None:
        invalid_row = list(VALID_ROW)
        invalid_row[1] = "07/19/2026"
        with self.assertRaisesRegex(PreservationError, "invalid order_date"):
            validate_orders_bytes(make_csv(tuple(invalid_row)))


class PreserveOrdersTests(unittest.TestCase):
    def test_preserves_raw_bytes_checksum_and_metadata(self) -> None:
        data = make_csv(VALID_ROW)
        captured_at = datetime(2026, 7, 20, 3, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            result = preserve_orders_bytes(
                data,
                source_url="https://example.test/orders.csv",
                resolved_url="https://cdn.example.test/orders.csv",
                orders_root=root,
                captured_at=captured_at,
            )

            date_directory = root / "2026-07-19"
            self.assertEqual(result.status, "preserved")
            self.assertEqual((date_directory / "orders.csv").read_bytes(), data)
            self.assertEqual(
                (date_directory / "orders.csv.sha256").read_text(encoding="utf-8"),
                f"{sha256_bytes(data)}  orders.csv\n",
            )
            metadata = json.loads(
                (date_directory / "capture.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["captured_at_utc"], "2026-07-20T03:30:00Z")
            self.assertEqual(metadata["order_date"], "2026-07-19")
            self.assertEqual(metadata["row_count"], 1)
            self.assertEqual(metadata["column_count"], 9)
            self.assertEqual(metadata["sha256"], sha256_bytes(data))

    def test_repeat_with_same_file_is_no_op(self) -> None:
        data = make_csv(VALID_ROW)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = preserve_orders_bytes(
                data,
                source_url="https://example.test/orders.csv",
                resolved_url="https://example.test/orders.csv",
                orders_root=root,
            )
            metadata_before = (root / "2026-07-19" / "capture.json").read_bytes()
            second = preserve_orders_bytes(
                data,
                source_url="https://example.test/orders.csv",
                resolved_url="https://example.test/orders.csv",
                orders_root=root,
            )
            metadata_after = (root / "2026-07-19" / "capture.json").read_bytes()

            self.assertEqual(first.status, "preserved")
            self.assertEqual(second.status, "already_preserved")
            self.assertEqual(metadata_before, metadata_after)

    def test_different_existing_file_is_never_overwritten(self) -> None:
        original = make_csv(VALID_ROW)
        changed_row = list(VALID_ROW)
        changed_row[3] = "P1999"
        changed = make_csv(tuple(changed_row))
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            preserve_orders_bytes(
                original,
                source_url="https://example.test/orders.csv",
                resolved_url="https://example.test/orders.csv",
                orders_root=root,
            )
            with self.assertRaisesRegex(PreservationError, "different contents"):
                preserve_orders_bytes(
                    changed,
                    source_url="https://example.test/orders.csv",
                    resolved_url="https://example.test/orders.csv",
                    orders_root=root,
                )
            self.assertEqual(
                (root / "2026-07-19" / "orders.csv").read_bytes(), original
            )

    def test_dry_run_creates_nothing(self) -> None:
        data = make_csv(VALID_ROW)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            result = preserve_orders_bytes(
                data,
                source_url="https://example.test/orders.csv",
                resolved_url="https://example.test/orders.csv",
                orders_root=root,
                dry_run=True,
            )
            self.assertEqual(result.status, "would_preserve")
            self.assertEqual(list(root.iterdir()), [])

    def test_incomplete_existing_directory_is_not_modified(self) -> None:
        data = make_csv(VALID_ROW)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            incomplete_directory = root / "2026-07-19"
            incomplete_directory.mkdir()
            marker = incomplete_directory / "investigate.txt"
            marker.write_text("keep me", encoding="utf-8")

            with self.assertRaisesRegex(PreservationError, "without orders.csv"):
                preserve_orders_bytes(
                    data,
                    source_url="https://example.test/orders.csv",
                    resolved_url="https://example.test/orders.csv",
                    orders_root=root,
                )

            self.assertEqual(marker.read_text(encoding="utf-8"), "keep me")

    def test_incorrect_recorded_checksum_is_rejected(self) -> None:
        data = make_csv(VALID_ROW)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            preserve_orders_bytes(
                data,
                source_url="https://example.test/orders.csv",
                resolved_url="https://example.test/orders.csv",
                orders_root=root,
            )
            checksum_path = root / "2026-07-19" / "orders.csv.sha256"
            checksum_path.write_text(f"{'0' * 64}  orders.csv\n", encoding="utf-8")
            with self.assertRaisesRegex(PreservationError, "does not match"):
                preserve_orders_bytes(
                    data,
                    source_url="https://example.test/orders.csv",
                    resolved_url="https://example.test/orders.csv",
                    orders_root=root,
                )


if __name__ == "__main__":
    unittest.main()

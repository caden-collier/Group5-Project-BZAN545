from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from bzan545.ingestion import LOG_FIELDS, run_ingestion
from bzan545.orders import NEW_PRODUCT_ID_COLUMNS, PreservationError


FIXED_TIME = datetime(2026, 7, 31, 2, 37, tzinfo=timezone.utc)
VALID_ROW = "20260731-0001,2026-07-31,S005,NP5047,1,58.07,0,ship_from_store,N"


def download_valid_csv() -> bytes:
    return (",".join(NEW_PRODUCT_ID_COLUMNS) + "\n" + VALID_ROW + "\n").encode()


class IngestionTests(unittest.TestCase):
    def test_success_is_preserved_logged_and_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            options = dict(
                log_path=root / "log.csv", bronze_root=root / "bronze",
                downloader=download_valid_csv, now=lambda: FIXED_TIME,
            )
            self.assertTrue(run_ingestion(**options).succeeded)
            self.assertTrue(run_ingestion(**options).succeeded)
            with options["log_path"].open(newline="") as log_file:
                rows = list(csv.DictReader(log_file))
            self.assertEqual(len(rows), 1)
            self.assertEqual(tuple(rows[0]), LOG_FIELDS)
            self.assertEqual(rows[0]["status"], "success")

    def test_failure_is_logged_and_returns_failure(self) -> None:
        def fail() -> bytes:
            raise PreservationError("network unavailable")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            result = run_ingestion(
                log_path=root / "log.csv", bronze_root=root / "bronze",
                downloader=fail, now=lambda: FIXED_TIME,
            )
            self.assertFalse(result.succeeded)
            self.assertIn("network unavailable", (root / "log.csv").read_text())


if __name__ == "__main__":
    unittest.main()

"""Checks against the generated analytics outputs."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

import pandas as pd


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

PROCESSED_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

PRODUCT_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "products"
    / "2026-07-29"
)


class AnalyticsOutputTests(
    unittest.TestCase
):
    """Validate the actual generated outputs."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.clean = pd.read_csv(
            PROCESSED_DIR
            / "order_lines_clean.csv"
        )

        cls.reconciled = pd.read_csv(
            PROCESSED_DIR
            / "order_lines_reconciled.csv"
        )

        cls.daily = pd.read_csv(
            PROCESSED_DIR
            / "daily_sales.csv"
        )

        cls.final = pd.read_csv(
            PROCESSED_DIR
            / "daily_sales_weather.csv"
        )

        cls.summary = json.loads(
            (
                PROCESSED_DIR
                / "order_cleaning_summary.json"
            )
            .read_text(
                encoding="utf-8"
            )
        )

    def test_four_exact_duplicates_removed(
        self,
    ) -> None:
        self.assertEqual(
            int(
                self.summary[
                    "exact_duplicate_rows_removed"
                ]
            ),
            4,
        )

        self.assertEqual(
            int(
                self.summary["raw_row_count"]
            )
            - int(
                self.summary["clean_row_count"]
            ),
            4,
        )

    def test_clean_order_ids_are_unique(
        self,
    ) -> None:
        self.assertEqual(
            int(
                self.clean[
                    "order_id"
                ]
                .duplicated()
                .sum()
            ),
            0,
        )

    def test_reconciliation_preserves_rows(
        self,
    ) -> None:
        self.assertEqual(
            len(self.clean),
            len(self.reconciled),
        )

    def test_crosswalk_covers_new_products(
        self,
    ) -> None:
        new_products = pd.read_csv(
            PRODUCT_DIR
            / "new_products.csv"
        )

        crosswalk = pd.read_csv(
            PROCESSED_DIR
            / "product_crosswalk.csv"
        )

        self.assertEqual(
            set(
                new_products[
                    "new_product_id"
                ]
            ),
            set(
                crosswalk[
                    "new_product_id"
                ]
            ),
        )

    def test_final_grain_is_unique(
        self,
    ) -> None:
        grain = [
            "order_date",
            "store_id",
            "canonical_product_id",
        ]

        self.assertEqual(
            int(
                self.final
                .duplicated(grain)
                .sum()
            ),
            0,
        )

        self.assertEqual(
            len(self.daily),
            len(self.final),
        )

    def test_reference_joins_are_complete(
        self,
    ) -> None:
        store_flags = (
            self.final[
                "store_joined_flag"
            ]
            .astype(str)
            .str.lower()
        )

        weather_flags = (
            self.final[
                "weather_available_flag"
            ]
            .astype(str)
            .str.lower()
        )

        self.assertTrue(
            store_flags.eq("true").all()
        )

        self.assertTrue(
            weather_flags.eq("true").all()
        )

    def test_units_and_sales_are_preserved(
        self,
    ) -> None:
        source_units = pd.to_numeric(
            self.clean["quantity"],
            errors="raise",
        ).sum()

        final_units = pd.to_numeric(
            self.final["units_sold"],
            errors="raise",
        ).sum()

        source_sales = (
            pd.to_numeric(
                self.clean["quantity"],
                errors="raise",
            )
            * pd.to_numeric(
                self.clean["unit_price"],
                errors="raise",
            )
        ).sum()

        final_sales = pd.to_numeric(
            self.final["net_sales"],
            errors="raise",
        ).sum()

        self.assertEqual(
            float(source_units),
            float(final_units),
        )

        self.assertAlmostEqual(
            float(source_sales),
            float(final_sales),
            places=2,
        )


if __name__ == "__main__":
    unittest.main()
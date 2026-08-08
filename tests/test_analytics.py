"""Focused validation tests for the silver and gold outputs."""

from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd


SILVER_PATH = Path("data/silver/order_lines.csv")
GOLD_PATH = Path(
    "data/gold/group5_rto_daily_sales_weather.csv"
)


class AnalyticsOutputTests(unittest.TestCase):
    """Validate the required properties of the final outputs."""

    @classmethod
    def setUpClass(cls) -> None:
        if not SILVER_PATH.exists():
            raise FileNotFoundError(
                f"Missing silver output: {SILVER_PATH}"
            )

        if not GOLD_PATH.exists():
            raise FileNotFoundError(
                f"Missing gold output: {GOLD_PATH}"
            )

        cls.silver = pd.read_csv(SILVER_PATH)
        cls.gold = pd.read_csv(GOLD_PATH)

    def test_silver_order_ids_are_unique(self) -> None:
        duplicate_count = int(
            self.silver["order_id"]
            .duplicated()
            .sum()
        )

        self.assertEqual(duplicate_count, 0)

    def test_unknown_products_remain_separate(self) -> None:
        unknown_rows = self.silver[
            self.silver["canonical_product_name"]
            .astype(str)
            .str.startswith("Unknown Product (")
        ]

        self.assertTrue(
            unknown_rows["canonical_product_id"].notna().all()
        )

    def test_silver_product_attributes_are_complete(self) -> None:
        columns = [
            "canonical_brand",
            "canonical_category",
            "canonical_subcategory",
        ]

        self.assertTrue(set(columns) <= set(self.silver.columns))
        self.assertFalse(self.silver[columns].isna().any().any())

    def test_product_names_are_complete(self) -> None:
        self.assertEqual(
            int(
                self.silver[
                    "canonical_product_name"
                ]
                .isna()
                .sum()
            ),
            0,
        )

        self.assertEqual(
            int(
                self.gold[
                    "canonical_product_name"
                ]
                .isna()
                .sum()
            ),
            0,
        )

    def test_gold_grain_is_unique(self) -> None:
        grain = [
            "order_date",
            "store_id",
            "canonical_product_id",
        ]

        duplicate_count = int(
            self.gold
            .duplicated(subset=grain)
            .sum()
        )

        self.assertEqual(duplicate_count, 0)

    def test_units_and_sales_are_preserved(self) -> None:
        silver_units = float(
            self.silver["quantity"].sum()
        )

        gold_units = float(
            self.gold["units_sold"].sum()
        )

        silver_sales = round(
            float(self.silver["net_sales"].sum()),
            2,
        )

        gold_sales = round(
            float(self.gold["net_sales"].sum()),
            2,
        )

        self.assertEqual(silver_units, gold_units)
        self.assertEqual(silver_sales, gold_sales)


if __name__ == "__main__":
    unittest.main()

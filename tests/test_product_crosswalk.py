"""Tests for the product migration matching rules."""

from __future__ import annotations

import unittest

import pandas as pd

from bzan545.config import BRONZE_DIR, SILVER_DIR
from tools.build_product_crosswalk import (
    build_crosswalk,
    choose_columns,
    normalize,
    parse_price,
)


class ProductCrosswalkTests(unittest.TestCase):
    def test_normalization_ignores_case_and_punctuation(self) -> None:
        self.assertEqual(normalize("ACME's Trail-Shoe"), "acme s trail shoe")

    def test_price_parser_accepts_currency(self) -> None:
        self.assertEqual(parse_price("$1,299.50"), 1299.50)

    def test_exact_match_is_selected(self) -> None:
        legacy = [
            {
                "product_id": "P1001",
                "product_name": "Acme Trail Shoe",
                "brand": "Acme",
                "category": "Footwear",
                "list_price": "90.00",
            },
            {
                "product_id": "P1002",
                "product_name": "Acme Road Shoe",
                "brand": "Acme",
                "category": "Footwear",
                "list_price": "85.00",
            },
        ]
        migrated = [
            {
                "new_product_id": "NP5001",
                "product_name": "Acme Trail Shoe",
                "brand": "Acme",
                "category": "Footwear",
                "list_price": "90.00",
            }
        ]
        old_columns = choose_columns(legacy[0])
        new_columns = choose_columns(migrated[0])

        result = build_crosswalk(
            legacy, migrated, old_columns, new_columns
        )

        self.assertEqual(result[0]["proposed_legacy_product_id"], "P1001")
        self.assertEqual(result[0]["match_status"], "matched_exact")

    def test_duplicate_candidate_requires_review(self) -> None:
        legacy = [
            {"product_id": "P1001", "product_name": "Trail Shoe"},
            {"product_id": "P1002", "product_name": "Winter Hat"},
        ]
        migrated = [
            {"new_product_id": "NP5001", "product_name": "Trail Shoe"},
            {"new_product_id": "NP5002", "product_name": "Trail Shoe"},
        ]

        result = build_crosswalk(
            legacy,
            migrated,
            choose_columns(legacy[0]),
            choose_columns(migrated[0]),
        )

        self.assertTrue(
            all(
                row["match_status"] == "review_duplicate_candidate"
                for row in result
            )
        )

    def test_real_crosswalk_covers_the_real_product_snapshot(self) -> None:
        snapshot = BRONZE_DIR / "products" / "2026-07-29"
        legacy = pd.read_csv(snapshot / "products.csv")
        migrated = pd.read_csv(snapshot / "new_products.csv")
        crosswalk = pd.read_csv(SILVER_DIR / "product_crosswalk.csv")

        self.assertFalse(crosswalk["new_product_id"].duplicated().any())
        self.assertEqual(
            set(crosswalk["new_product_id"]), set(migrated["new_product_id"])
        )
        self.assertTrue(
            set(crosswalk["proposed_legacy_product_id"])
            <= set(legacy["product_id"])
        )
        self.assertTrue(crosswalk["match_score"].between(0, 1).all())


if __name__ == "__main__":
    unittest.main()

"""Tests for the product migration matching rules."""

from __future__ import annotations

import unittest

from src.build_product_crosswalk import (
    build_crosswalk,
    choose_columns,
    normalize,
    parse_price,
)
from src.preserve_daily_orders import validate_orders_bytes


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

    def test_migrated_order_schema_is_accepted(self) -> None:
        migrated_csv = (
            "order_id,order_date,store_id,new_product_id,quantity,unit_price,"
            "discount_pct,sales_channel,loyalty_member\n"
            "20260728-0001,2026-07-28,S008,NP5044,2,155.01,20,"
            "ship_from_store,Y\n"
        ).encode()

        result = validate_orders_bytes(migrated_csv)

        self.assertEqual(result.product_id_column, "new_product_id")


if __name__ == "__main__":
    unittest.main()

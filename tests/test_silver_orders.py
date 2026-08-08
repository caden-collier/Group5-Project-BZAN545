from __future__ import annotations

import unittest

import pandas as pd

from bzan545.silver_orders import build_product_dimension, parse_unit_prices


class SilverOrdersTests(unittest.TestCase):
    def test_plain_and_currency_prices_are_parsed(self) -> None:
        values = pd.Series(["72.70", "$72.70", "$1,234.56"])

        parsed = parse_unit_prices(values)

        self.assertEqual(parsed.tolist(), [72.70, 72.70, 1234.56])

    def test_invalid_price_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_unit_prices(pd.Series(["not-a-price"]))

    def test_product_dimension_includes_dashboard_attributes(self) -> None:
        crosswalk = pd.DataFrame(
            {
                "legacy_product_id": ["P1001"],
                "canonical_product_id": ["NP5001"],
                "canonical_product_name": ["Approved Trail Shoe"],
            }
        )
        legacy = pd.DataFrame(
            {
                "product_id": ["P1001"],
                "product_name": ["Old Trail Shoe"],
                "brand": ["Old Brand"],
                "category": ["footwear"],
                "subcategory": ["trail shoes"],
            }
        )
        migrated = pd.DataFrame(
            {
                "new_product_id": ["NP5001", "NP9001"],
                "item_name": ["New Trail Shoe", "Future Lantern"],
                "brand_name": ["New Brand", "Future Brand"],
                "department": ["footwear", "camping"],
                "class": ["trail shoes", "flashlight"],
            }
        )

        result = build_product_dimension(crosswalk, legacy, migrated)
        result = result.set_index("canonical_product_id")

        self.assertEqual(
            result.loc["NP5001", "canonical_product_name"],
            "Approved Trail Shoe",
        )
        self.assertEqual(
            result.loc["NP5001", "canonical_brand"],
            "New Brand",
        )
        self.assertEqual(
            result.loc["NP9001", "canonical_product_name"],
            "Future Lantern",
        )
        self.assertEqual(
            result.loc["NP9001", "canonical_category"],
            "camping",
        )


if __name__ == "__main__":
    unittest.main()

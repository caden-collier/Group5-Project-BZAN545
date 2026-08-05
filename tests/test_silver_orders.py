from __future__ import annotations

import unittest

import pandas as pd

from bzan545.silver_orders import parse_unit_prices


class SilverOrdersTests(unittest.TestCase):
    def test_plain_and_currency_prices_are_parsed(self) -> None:
        values = pd.Series(["72.70", "$72.70", "$1,234.56"])

        parsed = parse_unit_prices(values)

        self.assertEqual(parsed.tolist(), [72.70, 72.70, 1234.56])

    def test_invalid_price_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_unit_prices(pd.Series(["not-a-price"]))


if __name__ == "__main__":
    unittest.main()

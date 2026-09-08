"""Focused checks for the simple product crosswalk."""

from __future__ import annotations

import unittest

import pandas as pd

from bzan545.config import BRONZE_DIR, SILVER_DIR
from bzan545.crosswalk import build_crosswalk, normalize


def legacy_products(*rows: tuple[str, str, str, float]) -> pd.DataFrame:
    return pd.DataFrame(
        rows,
        columns=["product_id", "product_name", "brand", "base_price"],
    )


def new_products(*rows: tuple[str, str, str, float]) -> pd.DataFrame:
    return pd.DataFrame(
        rows,
        columns=["new_product_id", "item_name", "brand_name", "msrp"],
    )


class ProductCrosswalkTests(unittest.TestCase):
    def test_normalization_ignores_case_and_punctuation(self) -> None:
        self.assertEqual(normalize("ACME's Trail-Shoe"), "acme s trail shoe")

    def test_exact_name_match_is_selected(self) -> None:
        result = build_crosswalk(
            legacy_products(
                ("P1001", "Acme Trail Shoe", "Acme", 90.0),
                ("P1002", "Acme Road Shoe", "Acme", 85.0),
            ),
            new_products(("NP5001", "Acme Trail Shoe", "Acme", 90.0)),
        )

        self.assertEqual(result.loc[0, "proposed_legacy_product_id"], "P1001")
        self.assertEqual(result.loc[0, "match_status"], "exact_name_match")

    def test_non_exact_and_repeated_candidates_require_review(self) -> None:
        result = build_crosswalk(
            legacy_products(
                ("P1001", "Trail Shoe", "Acme", 90.0),
                ("P1002", "Winter Hat", "Acme", 25.0),
            ),
            new_products(
                ("NP5001", "Trail Shoe Pro", "Acme", 92.0),
                ("NP5002", "Trail Shoe Alt", "Acme", 88.0),
            ),
        )

        self.assertTrue(result["match_status"].eq("review_required").all())
        self.assertTrue(
            result["review_note"].str.contains("Multiple new products").all()
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

    def test_review_register_matches_the_canonical_decisions(self) -> None:
        proposals = pd.read_csv(SILVER_DIR / "product_crosswalk.csv")
        reviews = pd.read_csv(SILVER_DIR / "product_crosswalk_review.csv")
        canonical = pd.read_csv(
            SILVER_DIR / "canonical_product_crosswalk.csv",
            dtype={"legacy_product_id": "string"},
        )

        flagged_ids = set(
            proposals.loc[
                proposals["match_status"].eq("review_required"),
                "new_product_id",
            ]
        )
        self.assertEqual(set(reviews["new_product_id"]), flagged_ids)
        self.assertFalse(reviews["new_product_id"].duplicated().any())
        self.assertTrue(reviews["review_basis"].str.strip().ne("").all())
        self.assertTrue(reviews["reviewed_on"].str.fullmatch(r"\d{4}-\d{2}-\d{2}").all())
        self.assertTrue(
            set(reviews["review_decision"])
            <= {"accepted", "corrected", "no_legacy_predecessor"}
        )

        canonical_by_new = canonical.set_index("canonical_product_id")[
            "legacy_product_id"
        ]
        for review in reviews.itertuples(index=False):
            actual = canonical_by_new.loc[review.new_product_id]
            expected = review.canonical_legacy_product_id
            if review.review_decision == "no_legacy_predecessor":
                self.assertTrue(pd.isna(actual))
                self.assertTrue(pd.isna(expected))
            else:
                self.assertEqual(actual, expected)

        mapped = canonical["legacy_product_id"].dropna()
        self.assertFalse(mapped.duplicated().any())
        self.assertFalse(canonical["canonical_product_id"].duplicated().any())
        self.assertIn("corrected", set(reviews["review_decision"]))


if __name__ == "__main__":
    unittest.main()

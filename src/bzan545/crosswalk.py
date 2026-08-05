"""Build a small, reviewable mapping from new products to legacy products."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from .config import BRONZE_DIR, SILVER_DIR


PRODUCT_SNAPSHOT_DIR = BRONZE_DIR / "products" / "2026-07-29"
LEGACY_PRODUCTS_PATH = PRODUCT_SNAPSHOT_DIR / "products.csv"
NEW_PRODUCTS_PATH = PRODUCT_SNAPSHOT_DIR / "new_products.csv"
CROSSWALK_PATH = SILVER_DIR / "product_crosswalk.csv"
SUMMARY_PATH = SILVER_DIR / "product_crosswalk_summary.json"

LEGACY_COLUMNS = {"product_id", "product_name", "brand", "base_price"}
NEW_COLUMNS = {"new_product_id", "item_name", "brand_name", "msrp"}


def normalize(value: object) -> str:
    """Make names comparable without hiding meaningful words."""
    text = str(value or "").casefold().replace("&", " and ")
    return " ".join(re.findall(r"[a-z0-9]+", text))


def text_similarity(left: object, right: object) -> float:
    """Return a straightforward character similarity from zero to one."""
    return SequenceMatcher(None, normalize(left), normalize(right)).ratio()


def price_similarity(left: object, right: object) -> float:
    """Return one for equal prices and approach zero as prices diverge."""
    left_price = float(left)
    right_price = float(right)
    return max(
        0.0,
        1.0 - abs(left_price - right_price) / max(left_price, right_price, 1.0),
    )


def candidate_score(new_product: pd.Series, legacy_product: pd.Series) -> float:
    """Rank candidates using name (70%), brand (20%), and price (10%)."""
    return (
        0.70
        * text_similarity(new_product["item_name"], legacy_product["product_name"])
        + 0.20
        * text_similarity(new_product["brand_name"], legacy_product["brand"])
        + 0.10
        * price_similarity(new_product["msrp"], legacy_product["base_price"])
    )


def validate_products(
    frame: pd.DataFrame,
    *,
    required_columns: set[str],
    id_column: str,
) -> None:
    """Check only the source conditions needed to build a trustworthy mapping."""
    missing = required_columns - set(frame.columns)
    if missing:
        raise ValueError(f"Product data is missing columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError("Product data contains no rows.")
    if frame[id_column].isna().any() or frame[id_column].astype(str).str.strip().eq("").any():
        raise ValueError(f"Product data contains a blank {id_column}.")
    if frame[id_column].duplicated().any():
        raise ValueError(f"Product data contains duplicate {id_column} values.")


def build_crosswalk(
    legacy_products: pd.DataFrame,
    new_products: pd.DataFrame,
) -> pd.DataFrame:
    """Choose one proposed legacy candidate for every new product."""
    validate_products(
        legacy_products,
        required_columns=LEGACY_COLUMNS,
        id_column="product_id",
    )
    validate_products(
        new_products,
        required_columns=NEW_COLUMNS,
        id_column="new_product_id",
    )

    rows: list[dict[str, object]] = []
    for _, new_product in new_products.iterrows():
        candidates = []
        for _, legacy_product in legacy_products.iterrows():
            candidates.append(
                (
                    candidate_score(new_product, legacy_product),
                    str(legacy_product["product_id"]),
                    str(legacy_product["product_name"]),
                )
            )
        candidates.sort(key=lambda candidate: (-candidate[0], candidate[1]))
        normalized_new_name = normalize(new_product["item_name"]).replace(" ", "")
        exact_candidates = [
            candidate
            for candidate in candidates
            if normalize(candidate[2]).replace(" ", "") == normalized_new_name
        ]
        best = exact_candidates[0] if exact_candidates else candidates[0]
        runner_up = next(candidate for candidate in candidates if candidate != best)
        exact_name = bool(exact_candidates)
        rows.append(
            {
                "new_product_id": new_product["new_product_id"],
                "new_product_name": new_product["item_name"],
                "proposed_legacy_product_id": best[1],
                "proposed_legacy_product_name": best[2],
                "match_status": "exact_name_match" if exact_name else "review_required",
                "match_score": round(best[0], 4),
                "runner_up_legacy_product_id": runner_up[1],
                "runner_up_score": round(runner_up[0], 4),
                "review_note": (
                    "Normalized product names match."
                    if exact_name
                    else "Candidate is a suggestion; confirm it manually."
                ),
            }
        )

    crosswalk = pd.DataFrame(rows)
    repeated_candidates = crosswalk["proposed_legacy_product_id"].duplicated(
        keep=False
    )
    crosswalk.loc[repeated_candidates, "match_status"] = "review_required"
    crosswalk.loc[repeated_candidates, "review_note"] = (
        "Multiple new products propose this legacy product; confirm manually."
    )
    return crosswalk


def build_crosswalk_files(
    legacy_path: Path = LEGACY_PRODUCTS_PATH,
    new_path: Path = NEW_PRODUCTS_PATH,
    output_path: Path = CROSSWALK_PATH,
    summary_path: Path = SUMMARY_PATH,
) -> pd.DataFrame:
    """Read the bronze snapshots and write the silver mapping and summary."""
    legacy_products = pd.read_csv(legacy_path)
    new_products = pd.read_csv(new_path)
    crosswalk = build_crosswalk(legacy_products, new_products)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    crosswalk.to_csv(output_path, index=False)
    status_counts = crosswalk["match_status"].value_counts().to_dict()
    summary = {
        "legacy_rows": len(legacy_products),
        "new_rows": len(new_products),
        "status_counts": status_counts,
        "scoring": {"name": 0.70, "brand": 0.20, "price": 0.10},
        "note": "Every non-exact or repeated candidate requires human review.",
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Crosswalk: {output_path} ({len(crosswalk)} rows)")
    print(f"Status counts: {status_counts}")
    return crosswalk

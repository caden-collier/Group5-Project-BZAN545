"""Apply the product crosswalk without forcing uncertain matches."""

from __future__ import annotations

import json

import pandas as pd

from bzan545.config import DATA_DIR


INPUT_PATH = (
    DATA_DIR
    / "processed"
    / "order_lines_clean.csv"
)

OUTPUT_PATH = (
    DATA_DIR
    / "processed"
    / "order_lines_reconciled.csv"
)

SUMMARY_PATH = (
    DATA_DIR
    / "processed"
    / "product_reconciliation_summary.json"
)

PRODUCT_SNAPSHOT_DIR = (
    DATA_DIR
    / "raw"
    / "products"
    / "2026-07-29"
)

LEGACY_PRODUCTS_PATH = (
    PRODUCT_SNAPSHOT_DIR
    / "products.csv"
)

NEW_PRODUCTS_PATH = (
    PRODUCT_SNAPSHOT_DIR
    / "new_products.csv"
)

CROSSWALK_PATH = (
    DATA_DIR
    / "processed"
    / "product_crosswalk.csv"
)

TRUSTED_STATUSES = {
    "matched_exact",
    "matched_high_confidence",
}


class ProductReconciliationError(
    RuntimeError
):
    """Raised when products cannot be reconciled safely."""


def reconcile_order_products() -> pd.DataFrame:
    """Create one product key across both systems."""

    orders = pd.read_csv(
        INPUT_PATH,
        dtype={
            "product_id": "string",
            "new_product_id": "string",
        },
    )

    legacy_products = pd.read_csv(
        LEGACY_PRODUCTS_PATH,
        dtype={
            "product_id": "string",
        },
    )

    new_products = pd.read_csv(
        NEW_PRODUCTS_PATH,
        dtype={
            "new_product_id": "string",
        },
    )

    crosswalk = pd.read_csv(
        CROSSWALK_PATH,
        dtype={
            "new_product_id": "string",
            "proposed_legacy_product_id":
                "string",
        },
    )

    required_crosswalk_columns = {
        "new_product_id",
        "proposed_legacy_product_id",
        "match_status",
        "match_score",
        "review_note",
    }

    missing_crosswalk_columns = (
        required_crosswalk_columns
        - set(crosswalk.columns)
    )

    if missing_crosswalk_columns:
        raise ProductReconciliationError(
            "Crosswalk is missing columns: "
            f"{sorted(missing_crosswalk_columns)}"
        )

    for frame, key, source in [
        (
            legacy_products,
            "product_id",
            LEGACY_PRODUCTS_PATH,
        ),
        (
            new_products,
            "new_product_id",
            NEW_PRODUCTS_PATH,
        ),
        (
            crosswalk,
            "new_product_id",
            CROSSWALK_PATH,
        ),
    ]:
        if frame[key].duplicated().any():
            raise ProductReconciliationError(
                f"Duplicate {key} values "
                f"found in {source}"
            )

    result = orders.merge(
        crosswalk[
            [
                "new_product_id",
                "proposed_legacy_product_id",
                "match_status",
                "match_score",
                "review_note",
            ]
        ],
        on="new_product_id",
        how="left",
        validate="many_to_one",
    )

    is_legacy = (
        result["product_system"]
        .eq("legacy")
    )

    is_trusted_match = (
        result["match_status"]
        .isin(TRUSTED_STATUSES)
    )

    result["source_product_id"] = (
        result["product_id"]
        .fillna(
            result["new_product_id"]
        )
    )

    result[
        "product_reconciliation_status"
    ] = (
        result["match_status"]
        .fillna("unmapped_new_product")
    )

    result.loc[
        is_legacy,
        "product_reconciliation_status",
    ] = "legacy_original"

    result[
        "product_reconciled_flag"
    ] = (
        is_legacy
        | is_trusted_match
    )

    # Legacy rows keep their existing product_id.
    result["canonical_product_id"] = (
        result["product_id"]
    )

    # Only trusted mappings are assigned
    # the historical legacy product ID.
    result.loc[
        ~is_legacy & is_trusted_match,
        "canonical_product_id",
    ] = result.loc[
        ~is_legacy & is_trusted_match,
        "proposed_legacy_product_id",
    ]

    # Unresolved migrated products remain separate.
    unresolved = (
        ~is_legacy
        & ~is_trusted_match
    )

    result.loc[
        unresolved,
        "canonical_product_id",
    ] = (
        "NEW:"
        + result.loc[
            unresolved,
            "new_product_id",
        ].astype(str)
    )

    if result[
        "canonical_product_id"
    ].isna().any():
        raise ProductReconciliationError(
            "At least one row is missing "
            "canonical_product_id"
        )

    legacy_dimension = (
        legacy_products[
            [
                "product_id",
                "product_name",
                "category",
                "subcategory",
                "brand",
            ]
        ]
        .rename(
            columns={
                "product_id":
                    "canonical_product_id",

                "product_name":
                    "legacy_product_name",

                "category":
                    "legacy_category",

                "subcategory":
                    "legacy_subcategory",

                "brand":
                    "legacy_brand",
            }
        )
    )

    new_dimension = (
        new_products[
            [
                "new_product_id",
                "item_name",
                "department",
                "class",
                "brand_name",
            ]
        ]
        .rename(
            columns={
                "item_name":
                    "new_product_name",

                "department":
                    "new_category",

                "class":
                    "new_subcategory",

                "brand_name":
                    "new_brand",
            }
        )
    )

    result = result.merge(
        legacy_dimension,
        on="canonical_product_id",
        how="left",
        validate="many_to_one",
    )

    result = result.merge(
        new_dimension,
        on="new_product_id",
        how="left",
        validate="many_to_one",
    )

    result["canonical_product_name"] = (
        result["legacy_product_name"]
        .fillna(
            result["new_product_name"]
        )
    )

    result["canonical_category"] = (
        result["legacy_category"]
        .fillna(
            result["new_category"]
        )
    )

    result["canonical_subcategory"] = (
        result["legacy_subcategory"]
        .fillna(
            result["new_subcategory"]
        )
    )

    result["canonical_brand"] = (
        result["legacy_brand"]
        .fillna(
            result["new_brand"]
        )
    )

    result["canonical_product_name"] = (
        result["canonical_product_name"]
        .fillna(
            "Unmapped product "
            + result[
                "source_product_id"
            ].astype(str)
        )
    )

    for column in [
        "canonical_category",
        "canonical_subcategory",
        "canonical_brand",
    ]:
        result[column] = (
            result[column]
            .fillna("unmapped")
        )

    result.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    summary = {
        "input_rows":
            int(len(orders)),

        "output_rows":
            int(len(result)),

        "status_counts": {
            str(status): int(count)
            for status, count
            in result[
                "product_reconciliation_status"
            ]
            .value_counts(dropna=False)
            .items()
        },

        "unmapped_new_product_ids":
            sorted(
                result.loc[
                    result[
                        "product_reconciliation_status"
                    ].eq(
                        "unmapped_new_product"
                    ),
                    "new_product_id",
                ]
                .dropna()
                .unique()
                .tolist()
            ),
    }

    SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "Wrote:",
        OUTPUT_PATH.relative_to(
            DATA_DIR.parent
        ),
    )

    print(
        json.dumps(
            summary,
            indent=2,
        )
    )

    return result


if __name__ == "__main__":
    reconcile_order_products()
"""Build the cleaned and reconciled silver order-line file."""

from __future__ import annotations

import pandas as pd

from .config import (
    BRONZE_DIR,
    BRONZE_ORDERS_DIR,
    PRODUCT_CROSSWALK_PATH,
    SILVER_ORDERS_PATH,
)

NEW_PRODUCTS_PATH = (
    BRONZE_DIR
    / "products"
    / "2026-07-29"
    / "new_products.csv"
)

LEGACY_PRODUCTS_PATH = (
    BRONZE_DIR
    / "products"
    / "2026-07-29"
    / "products.csv"
)

def parse_unit_prices(values: pd.Series) -> pd.Series:
    """Convert plain or dollar-formatted transaction prices to numbers."""
    cleaned = (
        values.astype("string")
        .str.strip()
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
    )
    return pd.to_numeric(cleaned, errors="raise")


def read_bronze_orders() -> pd.DataFrame:
    """Read and combine every preserved bronze order file."""
    order_files = sorted(
        BRONZE_ORDERS_DIR.glob("*/orders.csv")
    )

    if not order_files:
        raise ValueError(
            f"No bronze order files found in {BRONZE_ORDERS_DIR}"
        )

    frames = []

    for path in order_files:
        daily_orders = pd.read_csv(path)

        # Legacy files use product_id.
        # Post-migration files use new_product_id.
        if "product_id" not in daily_orders.columns:
            daily_orders["product_id"] = pd.NA

        if "new_product_id" not in daily_orders.columns:
            daily_orders["new_product_id"] = pd.NA

        frames.append(daily_orders)

    orders = pd.concat(
        frames,
        ignore_index=True,
        sort=False,
    )

    for column in [
        "order_id",
        "store_id",
        "product_id",
        "new_product_id",
    ]:
        orders[column] = orders[column].astype("string")

    orders["order_date"] = pd.to_datetime(
        orders["order_date"],
        errors="raise",
    ).dt.strftime("%Y-%m-%d")

    orders["quantity"] = pd.to_numeric(
        orders["quantity"],
        errors="raise",
    )

    orders["unit_price"] = parse_unit_prices(
        orders["unit_price"]
    )

    orders["discount_pct"] = pd.to_numeric(
        orders["discount_pct"],
        errors="raise",
    )

    return orders


def build_silver_orders() -> pd.DataFrame:
    """Clean orders, reconcile products, and write the silver file."""

    orders = read_bronze_orders()

    raw_rows = len(orders)

    # Remove completely identical rows.
    orders = orders.drop_duplicates().copy()

    duplicates_removed = raw_rows - len(orders)

    duplicate_ids = sorted(
        orders.loc[
            orders["order_id"].duplicated(keep=False),
            "order_id",
        ]
        .dropna()
        .unique()
        .tolist()
    )

    if duplicate_ids:
        raise ValueError(
            "Conflicting rows remain for these order IDs: "
            + ", ".join(duplicate_ids)
        )

    # ----------------------------------------------------------
    # Load canonical crosswalk
    # ----------------------------------------------------------
    crosswalk = pd.read_csv(
    PRODUCT_CROSSWALK_PATH,
    dtype="string",
    )

    # legacy -> canonical id
    canonical_id_lookup = (
        crosswalk
        .dropna(subset=["legacy_product_id"])
        .set_index("legacy_product_id")["canonical_product_id"]
    )

    # canonical id -> product name
    canonical_name_lookup = (
        crosswalk
        .set_index("canonical_product_id")["canonical_product_name"]
    )

    orders["canonical_product_id"] = (
        orders["product_id"]
        .map(canonical_id_lookup)
    )

    # New orders are already canonical.
    new_orders = (
        orders["new_product_id"].notna()
        & orders["canonical_product_id"].isna()
    )

    orders.loc[
        new_orders,
        "canonical_product_id",
    ] = orders.loc[
        new_orders,
        "new_product_id",
    ]
    
    # First try the canonical crosswalk.
    orders["canonical_product_name"] = (
        orders["canonical_product_id"]
        .map(canonical_name_lookup)
    )

    # Then fall back to the product master for future products.
    new_products = pd.read_csv(
        NEW_PRODUCTS_PATH,
        dtype="string",
    )

    new_name_lookup = (
        new_products
        .set_index("new_product_id")["item_name"]
    )

    legacy_products = pd.read_csv(
    LEGACY_PRODUCTS_PATH,
    dtype="string",
    )

    legacy_name_lookup = (
        legacy_products
        .set_index("product_id")["product_name"]
    )

    missing = orders["canonical_product_name"].isna()

    orders.loc[
        missing,
        "canonical_product_name",
    ] = (
        orders.loc[
            missing,
            "canonical_product_id",
        ].map(new_name_lookup)
    )

    # ----------------------------------------------------------
    # Preserve legacy products that have no replacement.
    # ----------------------------------------------------------

    unmatched_legacy = (
        orders["canonical_product_id"].isna()
        & orders["product_id"].notna()
    )

    orders.loc[
        unmatched_legacy,
        "canonical_product_id",
    ] = orders.loc[
        unmatched_legacy,
        "product_id",
    ]

    orders.loc[
        unmatched_legacy,
        "canonical_product_name",
    ] = (
        orders.loc[
            unmatched_legacy,
            "product_id",
        ]
        .map(legacy_name_lookup)
    )

    # Final validation.
    missing = orders["canonical_product_id"].isna()

    if missing.any():
        print(
            "\nUnexpected orders still missing canonical IDs:\n"
        )

        print(
            orders.loc[
                missing,
                [
                    "order_id",
                    "product_id",
                    "new_product_id",
                ],
            ]
        )

        raise ValueError(
            f"{missing.sum()} orders still have no canonical product ID."
        )
    

    # unit_price is already the transaction selling price.
    orders["net_sales"] = (
        orders["quantity"]
        * orders["unit_price"]
    ).round(2)

    output_columns = [
        "order_id",
        "order_date",
        "store_id",
        "product_id",
        "new_product_id",
        "canonical_product_id",
        "canonical_product_name",
        "quantity",
        "unit_price",
        "discount_pct",
        "net_sales",
        "sales_channel",
        "loyalty_member",
    ]

    orders = (
        orders[output_columns]
        .sort_values(
            [
                "order_date",
                "order_id",
            ]
        )
        .reset_index(drop=True)
    )

    SILVER_ORDERS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    orders.to_csv(
        SILVER_ORDERS_PATH,
        index=False,
        lineterminator="\n",
    )

    print(
        "Silver orders complete:"
        f"\n  Raw rows: {raw_rows}"
        f"\n  Exact duplicates removed: {duplicates_removed}"
        f"\n  Silver rows: {len(orders)}"
        f"\n  Output: {SILVER_ORDERS_PATH}"
    )

    return orders


if __name__ == "__main__":
    build_silver_orders()

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

    orders["canonical_product_id"] = pd.NA
    orders["canonical_product_name"] = pd.NA

    # -------------------------------
    # Legacy orders
    # -------------------------------

    legacy_orders = orders["product_id"].notna()

    orders = orders.merge(
        crosswalk,
        left_on="product_id",
        right_on="legacy_product_id",
        how="left",
    )

    orders.loc[
        legacy_orders,
        "canonical_product_id",
    ] = orders.loc[
        legacy_orders,
        "canonical_product_id_y",
    ]

    orders.loc[
        legacy_orders,
        "canonical_product_name",
    ] = orders.loc[
        legacy_orders,
        "canonical_product_name_y",
    ]

    # -------------------------------
    # Orders already using the new catalog
    # -------------------------------

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

    # Lookup names for brand new products

    new_products = pd.read_csv(
        NEW_PRODUCTS_PATH,
        dtype="string",
    )[
        [
            "new_product_id",
            "item_name",
        ]
    ]

    name_lookup = (
        new_products
        .set_index("new_product_id")["item_name"]
    )

    missing_names = (
        orders["canonical_product_name"].isna()
    )

    orders.loc[
        missing_names,
        "canonical_product_name",
    ] = (
        orders.loc[
            missing_names,
            "canonical_product_id",
        ]
        .map(name_lookup)
    )

    # Final validation

    if orders["canonical_product_id"].isna().any():
        missing = (
            orders.loc[
                orders["canonical_product_id"].isna(),
                "order_id",
            ]
            .tolist()
        )

        raise ValueError(
            "Orders missing canonical product IDs: "
            + ", ".join(missing)
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

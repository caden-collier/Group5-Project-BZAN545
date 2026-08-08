"""Build the cleaned and reconciled silver order-line file."""

from __future__ import annotations

import pandas as pd

from .config import (
    BRONZE_DIR,
    BRONZE_ORDERS_DIR,
    PRODUCT_CROSSWALK_PATH,
    SILVER_ORDERS_PATH,
)

PRODUCT_ATTRIBUTE_COLUMNS = [
    "canonical_product_name",
    "canonical_brand",
    "canonical_category",
    "canonical_subcategory",
]


def latest_product_snapshot() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the newest complete legacy/new product snapshot."""
    snapshot_dirs = sorted(
        path
        for path in (BRONZE_DIR / "products").iterdir()
        if path.is_dir()
        and (path / "products.csv").exists()
        and (path / "new_products.csv").exists()
    )

    if not snapshot_dirs:
        raise FileNotFoundError(
            "No complete product snapshot contains products.csv and "
            "new_products.csv."
        )

    snapshot = snapshot_dirs[-1]
    return (
        pd.read_csv(snapshot / "products.csv", dtype="string"),
        pd.read_csv(snapshot / "new_products.csv", dtype="string"),
    )


def build_product_dimension(
    crosswalk: pd.DataFrame,
    legacy_products: pd.DataFrame,
    new_products: pd.DataFrame,
) -> pd.DataFrame:
    """Create one dashboard-ready row for every known canonical product."""
    required_crosswalk = {
        "legacy_product_id",
        "canonical_product_id",
        "canonical_product_name",
    }
    required_legacy = {
        "product_id",
        "product_name",
        "brand",
        "category",
        "subcategory",
    }
    required_new = {
        "new_product_id",
        "item_name",
        "brand_name",
        "department",
        "class",
    }

    for label, frame, required in [
        ("crosswalk", crosswalk, required_crosswalk),
        ("legacy products", legacy_products, required_legacy),
        ("new products", new_products, required_new),
    ]:
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{label} are missing columns: {', '.join(missing)}")

    if crosswalk["canonical_product_id"].duplicated().any():
        raise ValueError("Crosswalk contains duplicate canonical product IDs.")

    approved_names = crosswalk.set_index("canonical_product_id")[
        "canonical_product_name"
    ]

    new_dimension = new_products[
        [
            "new_product_id",
            "item_name",
            "brand_name",
            "department",
            "class",
        ]
    ].rename(
        columns={
            "new_product_id": "canonical_product_id",
            "item_name": "source_product_name",
            "brand_name": "canonical_brand",
            "department": "canonical_category",
            "class": "canonical_subcategory",
        }
    )
    new_dimension["canonical_product_name"] = (
        new_dimension["canonical_product_id"]
        .map(approved_names)
        .fillna(new_dimension["source_product_name"])
    )
    new_dimension = new_dimension.drop(columns=["source_product_name"])

    missing_master_rows = crosswalk.loc[
        ~crosswalk["canonical_product_id"].isin(
            new_dimension["canonical_product_id"]
        ),
        ["canonical_product_id", "canonical_product_name"],
    ].copy()
    for column, value in {
        "canonical_brand": "Unknown Brand",
        "canonical_category": "Unknown Category",
        "canonical_subcategory": "Unknown Subcategory",
    }.items():
        missing_master_rows[column] = value

    mapped_legacy_ids = set(crosswalk["legacy_product_id"].dropna())
    unmatched_legacy = legacy_products.loc[
        ~legacy_products["product_id"].isin(mapped_legacy_ids),
        ["product_id", "product_name", "brand", "category", "subcategory"],
    ].rename(
        columns={
            "product_id": "canonical_product_id",
            "product_name": "canonical_product_name",
            "brand": "canonical_brand",
            "category": "canonical_category",
            "subcategory": "canonical_subcategory",
        }
    )

    dimension = pd.concat(
        [new_dimension, missing_master_rows, unmatched_legacy],
        ignore_index=True,
    )
    if dimension["canonical_product_id"].duplicated().any():
        raise ValueError("Product dimension contains duplicate canonical IDs.")

    return dimension[
        ["canonical_product_id", *PRODUCT_ATTRIBUTE_COLUMNS]
    ]


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

    # Legacy -> canonical ID. New IDs are already canonical.
    canonical_id_lookup = (
        crosswalk
        .dropna(subset=["legacy_product_id"])
        .set_index("legacy_product_id")["canonical_product_id"]
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
    # Preserve legacy products that have no canonical replacement.
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

    # Final ID validation.
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
    legacy_products, new_products = latest_product_snapshot()
    product_dimension = build_product_dimension(
        crosswalk,
        legacy_products,
        new_products,
    )
    orders = orders.merge(
        product_dimension,
        on="canonical_product_id",
        how="left",
        validate="many_to_one",
    )

    unknown_products = orders["canonical_product_name"].isna()
    orders.loc[unknown_products, "canonical_product_name"] = (
        "Unknown Product ("
        + orders.loc[unknown_products, "canonical_product_id"]
        + ")"
    )
    for column, value in {
        "canonical_brand": "Unknown Brand",
        "canonical_category": "Unknown Category",
        "canonical_subcategory": "Unknown Subcategory",
    }.items():
        orders[column] = orders[column].fillna(value)

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
        "canonical_brand",
        "canonical_category",
        "canonical_subcategory",
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

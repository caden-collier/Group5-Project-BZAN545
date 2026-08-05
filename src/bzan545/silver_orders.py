"""Build the cleaned and reconciled silver order-line file."""

from __future__ import annotations

import pandas as pd

from .config import (
    BRONZE_ORDERS_DIR,
    PRODUCT_CROSSWALK_PATH,
    SILVER_ORDERS_PATH,
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

    # Remove rows that are completely identical.
    orders = orders.drop_duplicates().copy()

    duplicates_removed = raw_rows - len(orders)

    # Any duplicate IDs remaining would represent conflicting records.
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

    crosswalk = pd.read_csv(
        PRODUCT_CROSSWALK_PATH,
        dtype={
            "new_product_id": "string",
            "proposed_legacy_product_id": "string",
            "match_status": "string",
        },
    )

    crosswalk = crosswalk[
        [
            "new_product_id",
            "new_product_name",
            "proposed_legacy_product_id",
            "proposed_legacy_product_name",
            "match_status",
        ]
    ]

    legacy_name_lookup = (
        crosswalk[
            [
                "proposed_legacy_product_id",
                "proposed_legacy_product_name",
            ]
        ]
        .dropna()
        .drop_duplicates(
            subset=["proposed_legacy_product_id"]
        )
        .set_index("proposed_legacy_product_id")[
            "proposed_legacy_product_name"
        ]
    )

    orders = orders.merge(
        crosswalk,
        on="new_product_id",
        how="left",
        validate="many_to_one",
    )

    new_product_mask = orders["new_product_id"].notna()

    missing_crosswalk = sorted(
        orders.loc[
            new_product_mask
            & orders["match_status"].isna(),
            "new_product_id",
        ]
        .dropna()
        .unique()
        .tolist()
    )

    missing_crosswalk_mask = (
        new_product_mask
        & orders["match_status"].isna()
    )

    if missing_crosswalk:
        print(
            "Warning: products missing from the crosswalk "
            "will remain separate: "
            + ", ".join(missing_crosswalk)
        )

    orders["canonical_product_id"] = pd.Series(
        pd.NA,
        index=orders.index,
        dtype="string",
    )

    orders["reconciliation_status"] = pd.Series(
        pd.NA,
        index=orders.index,
        dtype="string",
    )

    orders["canonical_product_name"] = pd.Series(
        pd.NA,
        index=orders.index,
        dtype="string",
    )

    legacy_mask = orders["product_id"].notna()

    exact_mask = (
        new_product_mask
        & orders["match_status"].eq("exact_name_match")
    )

    review_mask = (
        new_product_mask
        & orders["match_status"].eq("review_required")
    )

    unmapped_mask = missing_crosswalk_mask

    # Legacy products retain their existing IDs.
    orders.loc[
        legacy_mask,
        "canonical_product_id",
    ] = orders.loc[
        legacy_mask,
        "product_id",
    ]

    orders.loc[
        legacy_mask,
        "reconciliation_status",
    ] = "legacy_original"

    orders.loc[
        legacy_mask,
        "canonical_product_name",
    ] = orders.loc[
        legacy_mask,
        "product_id",
    ].map(legacy_name_lookup)

    # Exact matches use the proposed legacy ID.
    orders.loc[
        exact_mask,
        "canonical_product_id",
    ] = orders.loc[
        exact_mask,
        "proposed_legacy_product_id",
    ]

    orders.loc[
        exact_mask,
        "reconciliation_status",
    ] = "exact_name_match"

    orders.loc[
        exact_mask,
        "canonical_product_name",
    ] = orders.loc[
        exact_mask,
        "proposed_legacy_product_name",
    ]

    # Uncertain products remain separate.
    orders.loc[
        review_mask,
        "canonical_product_id",
    ] = (
        "NEW:"
        + orders.loc[
            review_mask,
            "new_product_id",
        ]
    )

    orders.loc[
        review_mask,
        "reconciliation_status",
    ] = "review_required"

    orders.loc[
        review_mask,
        "canonical_product_name",
    ] = orders.loc[
        review_mask,
        "new_product_name",
    ]

    # Preserve orders whose product ID is missing from the product master.
    orders.loc[
        unmapped_mask,
        "canonical_product_id",
    ] = (
        "UNMAPPED:"
        + orders.loc[
            unmapped_mask,
            "new_product_id",
        ]
    )

    orders.loc[
        unmapped_mask,
        "reconciliation_status",
    ] = "missing_from_crosswalk"

    orders.loc[
        unmapped_mask,
        "canonical_product_name",
    ] = (
        "Unknown product ("
        + orders.loc[
            unmapped_mask,
            "new_product_id",
        ]
        + ")"
    )

    missing_canonical_ids = int(
        orders["canonical_product_id"].isna().sum()
    )

    if missing_canonical_ids:
        raise ValueError(
            f"{missing_canonical_ids} orders have no canonical product ID."
        )

    missing_name_mask = orders[
        "canonical_product_name"
    ].isna()

    orders.loc[
        missing_name_mask,
        "canonical_product_name",
    ] = (
        "Unknown product ("
        + orders.loc[
            missing_name_mask,
            "canonical_product_id",
        ].astype("string")
        + ")"
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
        "proposed_legacy_product_id",
        "match_status",
        "reconciliation_status",
        "quantity",
        "unit_price",
        "discount_pct",
        "net_sales",
        "sales_channel",
        "loyalty_member",
    ]

    orders = orders[
        output_columns
    ].sort_values(
        [
            "order_date",
            "order_id",
        ]
    ).reset_index(
        drop=True
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

"""Aggregate reconciled order lines to daily store-product sales."""

from __future__ import annotations

import pandas as pd

from bzan545.config import DATA_DIR


INPUT_PATH = (
    DATA_DIR
    / "processed"
    / "order_lines_reconciled.csv"
)

OUTPUT_PATH = (
    DATA_DIR
    / "processed"
    / "daily_sales.csv"
)

GRAIN = [
    "order_date",
    "store_id",
    "canonical_product_id",
]


def combine_unique(
    values: pd.Series,
) -> str:
    """Combine distinct values without creating extra rows."""

    unique_values = sorted(
        values
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    return "|".join(unique_values)


def normalize_boolean(
    values: pd.Series,
) -> pd.Series:
    """Convert CSV boolean values to actual booleans."""

    if values.dtype == bool:
        return values

    normalized = (
        values
        .astype(str)
        .str.strip()
        .str.lower()
    )

    mapped = normalized.map(
        {
            "true": True,
            "false": False,
            "1": True,
            "0": False,
        }
    )

    if mapped.isna().any():
        invalid_values = sorted(
            normalized[
                mapped.isna()
            ]
            .unique()
            .tolist()
        )

        raise ValueError(
            "Could not interpret "
            "product_reconciled_flag values: "
            f"{invalid_values}"
        )

    return mapped.astype(bool)


def build_daily_sales() -> pd.DataFrame:
    """Build one row per date, store, and canonical product."""

    order_lines = pd.read_csv(
        INPUT_PATH
    )

    for column in [
        "quantity",
        "unit_price",
        "discount_pct",
    ]:
        order_lines[column] = pd.to_numeric(
            order_lines[column],
            errors="raise",
        )

    order_lines[
        "product_reconciled_flag"
    ] = normalize_boolean(
        order_lines[
            "product_reconciled_flag"
        ]
    )

    # unit_price is already the actual
    # post-discount selling price.
    order_lines["line_net_sales"] = (
        order_lines["quantity"]
        * order_lines["unit_price"]
    )

    order_lines[
        "discounted_line_flag"
    ] = (
        order_lines["discount_pct"]
        .gt(0)
    )

    daily_sales = (
        order_lines
        .groupby(
            GRAIN,
            as_index=False,
            dropna=False,
        )
        .agg(
            canonical_product_name=(
                "canonical_product_name",
                "first",
            ),

            canonical_category=(
                "canonical_category",
                "first",
            ),

            canonical_subcategory=(
                "canonical_subcategory",
                "first",
            ),

            canonical_brand=(
                "canonical_brand",
                "first",
            ),

            product_system=(
                "product_system",
                combine_unique,
            ),

            product_reconciliation_status=(
                "product_reconciliation_status",
                combine_unique,
            ),

            product_reconciled_flag=(
                "product_reconciled_flag",
                "all",
            ),

            order_count=(
                "order_id",
                "nunique",
            ),

            order_line_count=(
                "order_id",
                "size",
            ),

            units_sold=(
                "quantity",
                "sum",
            ),

            net_sales=(
                "line_net_sales",
                "sum",
            ),

            average_discount_pct=(
                "discount_pct",
                "mean",
            ),

            discounted_order_line_count=(
                "discounted_line_flag",
                "sum",
            ),
        )
        .sort_values(GRAIN)
        .reset_index(drop=True)
    )

    daily_sales[
        "average_net_unit_price"
    ] = (
        daily_sales["net_sales"]
        / daily_sales["units_sold"]
    )

    daily_sales["net_sales"] = (
        daily_sales["net_sales"]
        .round(2)
    )

    daily_sales[
        "average_net_unit_price"
    ] = (
        daily_sales[
            "average_net_unit_price"
        ]
        .round(2)
    )

    daily_sales[
        "average_discount_pct"
    ] = (
        daily_sales[
            "average_discount_pct"
        ]
        .round(2)
    )

    daily_sales.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print(
        "Wrote:",
        OUTPUT_PATH.relative_to(
            DATA_DIR.parent
        ),
    )

    print(
        "Rows:",
        len(daily_sales),
    )

    print(
        "Duplicate grain rows:",
        int(
            daily_sales
            .duplicated(GRAIN)
            .sum()
        ),
    )

    print(
        "Units:",
        int(
            daily_sales[
                "units_sold"
            ].sum()
        ),
    )

    print(
        "Net sales:",
        round(
            float(
                daily_sales[
                    "net_sales"
                ].sum()
            ),
            2,
        ),
    )

    return daily_sales


if __name__ == "__main__":
    build_daily_sales()
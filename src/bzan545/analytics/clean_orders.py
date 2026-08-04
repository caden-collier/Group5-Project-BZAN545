"""Read all raw orders and create a validated clean order-line file."""

from __future__ import annotations

import json
from datetime import timedelta

import pandas as pd

from bzan545.config import DATA_DIR, RAW_ORDERS_DIR


OUTPUT_PATH = (
    DATA_DIR
    / "processed"
    / "order_lines_clean.csv"
)

SUMMARY_PATH = (
    DATA_DIR
    / "processed"
    / "order_cleaning_summary.json"
)

COMMON_COLUMNS = [
    "order_id",
    "order_date",
    "store_id",
    "quantity",
    "unit_price",
    "discount_pct",
    "sales_channel",
    "loyalty_member",
]

PRODUCT_COLUMNS = [
    "product_id",
    "new_product_id",
]


class CleanOrdersError(RuntimeError):
    """Raised when raw order files cannot be cleaned safely."""


def missing_calendar_dates(
    order_dates: pd.Series,
) -> list[str]:
    """Return missing dates between the first and last captures."""

    dates = sorted(set(order_dates))

    if not dates:
        return []

    current_date = dates[0]
    final_date = dates[-1]
    present_dates = set(dates)

    missing_dates = []

    while current_date <= final_date:
        if current_date not in present_dates:
            missing_dates.append(
                current_date.isoformat()
            )

        current_date += timedelta(days=1)

    return missing_dates


def build_clean_orders() -> pd.DataFrame:
    """Combine raw files and remove exact duplicate rows."""

    paths = sorted(
        RAW_ORDERS_DIR.glob("*/orders.csv")
    )

    if not paths:
        raise CleanOrdersError(
            f"No raw order files found in "
            f"{RAW_ORDERS_DIR}"
        )

    frames = []

    for path in paths:
        frame = pd.read_csv(path)

        missing_columns = sorted(
            set(COMMON_COLUMNS)
            - set(frame.columns)
        )

        if missing_columns:
            raise CleanOrdersError(
                f"{path} is missing columns: "
                f"{missing_columns}"
            )

        has_legacy_key = (
            "product_id" in frame.columns
        )

        has_new_key = (
            "new_product_id" in frame.columns
        )

        if has_legacy_key == has_new_key:
            raise CleanOrdersError(
                f"{path} must contain exactly "
                "one product-key column"
            )

        if not has_legacy_key:
            frame["product_id"] = pd.NA

        if not has_new_key:
            frame["new_product_id"] = pd.NA

        frame["product_system"] = (
            "legacy"
            if has_legacy_key
            else "migrated"
        )

        frame["source_file"] = (
            path
            .relative_to(DATA_DIR.parent)
            .as_posix()
        )

        frame["source_folder_date"] = (
            path.parent.name
        )

        frames.append(frame)

    raw_orders = pd.concat(
        frames,
        ignore_index=True,
        sort=False,
    )

    raw_orders["order_date"] = (
        pd.to_datetime(
            raw_orders["order_date"],
            errors="raise",
        )
        .dt.date
    )

    folder_dates = (
        pd.to_datetime(
            raw_orders["source_folder_date"],
            errors="raise",
        )
        .dt.date
    )

    dates_match = (
        raw_orders["order_date"]
        .eq(folder_dates)
    )

    if not dates_match.all():
        bad_rows = raw_orders.loc[
            ~dates_match,
            [
                "source_file",
                "order_date",
                "source_folder_date",
            ],
        ]

        raise CleanOrdersError(
            "At least one order date does not "
            "match its source folder:\n"
            + bad_rows.to_string(index=False)
        )

    if raw_orders["order_id"].isna().any():
        raise CleanOrdersError(
            "At least one row has a missing order_id"
        )

    blank_order_ids = (
        raw_orders["order_id"]
        .astype(str)
        .str.strip()
        .eq("")
    )

    if blank_order_ids.any():
        raise CleanOrdersError(
            "At least one row has a blank order_id"
        )

    for column in [
        "quantity",
        "unit_price",
        "discount_pct",
    ]:
        raw_orders[column] = pd.to_numeric(
            raw_orders[column],
            errors="raise",
        )

    if raw_orders["quantity"].le(0).any():
        raise CleanOrdersError(
            "quantity must be greater than zero"
        )

    if raw_orders["unit_price"].lt(0).any():
        raise CleanOrdersError(
            "unit_price cannot be negative"
        )

    valid_discounts = (
        raw_orders["discount_pct"]
        .between(0, 100)
    )

    if not valid_discounts.all():
        raise CleanOrdersError(
            "discount_pct must be between 0 and 100"
        )

    exactly_one_product_key = (
        raw_orders["product_id"].notna()
        ^ raw_orders["new_product_id"].notna()
    )

    if not exactly_one_product_key.all():
        raise CleanOrdersError(
            "Each row must contain exactly "
            "one product ID"
        )

    business_columns = (
        COMMON_COLUMNS
        + PRODUCT_COLUMNS
    )

    exact_duplicate_mask = (
        raw_orders.duplicated(
            subset=business_columns,
            keep="first",
        )
    )

    clean_orders = raw_orders.loc[
        ~exact_duplicate_mask
    ].copy()

    # Exact duplicates have now been removed.
    # Any remaining repeated order ID represents
    # conflicting source records and should stop the build.
    conflicting_order_ids = clean_orders.loc[
        clean_orders["order_id"].duplicated(
            keep=False
        )
    ]

    if not conflicting_order_ids.empty:
        raise CleanOrdersError(
            "Duplicate order IDs remain after "
            "exact duplicates were removed:\n"
            + conflicting_order_ids.to_string(
                index=False
            )
        )

    clean_orders = (
        clean_orders
        .sort_values(
            [
                "order_date",
                "order_id",
            ]
        )
        .reset_index(drop=True)
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    clean_orders.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    summary = {
        "source_file_count":
            int(len(paths)),

        "source_date_count":
            int(
                clean_orders[
                    "order_date"
                ].nunique()
            ),

        "raw_row_count":
            int(len(raw_orders)),

        "exact_duplicate_rows_removed":
            int(
                exact_duplicate_mask.sum()
            ),

        "clean_row_count":
            int(len(clean_orders)),

        "unique_order_id_count":
            int(
                clean_orders[
                    "order_id"
                ].nunique()
            ),

        "missing_calendar_dates":
            missing_calendar_dates(
                clean_orders["order_date"]
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

    return clean_orders


if __name__ == "__main__":
    build_clean_orders()
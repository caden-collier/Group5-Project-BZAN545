"""Build and publish the analytics-ready gold sales table."""

from __future__ import annotations

import json

import pandas as pd
from sqlalchemy import text

from .config import (
    DatabaseSettings,
    GOLD_SALES_PATH,
    GOLD_VALIDATION_PATH,
    SILVER_ORDERS_PATH,
)
from .weather import create_engine


GOLD_TABLE_NAME = "group5_rto_daily_sales_weather"

GRAIN_COLUMNS = [
    "order_date",
    "store_id",
    "canonical_product_id",
]


def write_validation_report(report: dict) -> None:
    """Write the gold validation results as JSON."""
    GOLD_VALIDATION_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    GOLD_VALIDATION_PATH.write_text(
        json.dumps(
            report,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def build_gold_sales() -> pd.DataFrame:
    """Aggregate silver orders, join dimensions, and publish gold."""
    if not SILVER_ORDERS_PATH.exists():
        raise FileNotFoundError(
            f"Silver orders file not found: {SILVER_ORDERS_PATH}"
        )

    orders = pd.read_csv(
        SILVER_ORDERS_PATH,
        dtype={
            "order_id": "string",
            "store_id": "string",
            "canonical_product_id": "string",
        },
    )

    required_columns = {
        "order_id",
        "order_date",
        "store_id",
        "canonical_product_id",
        "canonical_product_name",
        "quantity",
        "net_sales",
    }

    missing_columns = sorted(
        required_columns - set(orders.columns)
    )

    if missing_columns:
        raise ValueError(
            "Silver orders are missing columns: "
            + ", ".join(missing_columns)
        )

    orders["order_date"] = pd.to_datetime(
        orders["order_date"],
        errors="raise",
    ).dt.strftime("%Y-%m-%d")

    orders["store_id"] = (
        orders["store_id"]
        .astype("string")
        .str.strip()
    )

    orders["canonical_product_id"] = (
        orders["canonical_product_id"]
        .astype("string")
        .str.strip()
    )

    orders["canonical_product_name"] = (
        orders["canonical_product_name"]
        .astype("string")
        .str.strip()
    )

    orders["quantity"] = pd.to_numeric(
        orders["quantity"],
        errors="raise",
    )

    orders["net_sales"] = pd.to_numeric(
        orders["net_sales"],
        errors="raise",
    )

    product_names = orders[
        [
            "canonical_product_id",
            "canonical_product_name",
        ]
    ].drop_duplicates()

    product_name_counts = (
        product_names.groupby(
            "canonical_product_id"
        )["canonical_product_name"]
        .nunique(dropna=False)
    )

    conflicting_product_names = (
        product_name_counts[
            product_name_counts > 1
        ].index.tolist()
    )

    if conflicting_product_names:
        raise ValueError(
            "Canonical products have conflicting names: "
            + ", ".join(conflicting_product_names)
        )

    product_names = product_names.drop_duplicates(
        subset=["canonical_product_id"]
    )

    daily_sales = (
        orders.groupby(
            GRAIN_COLUMNS,
            as_index=False,
            dropna=False,
        )
        .agg(
            order_count=("order_id", "nunique"),
            units_sold=("quantity", "sum"),
            net_sales=("net_sales", "sum"),
        )
    )

    daily_sales["net_sales"] = (
        daily_sales["net_sales"].round(2)
    )

    daily_sales = daily_sales.merge(
        product_names,
        on="canonical_product_id",
        how="left",
        validate="many_to_one",
    )

    settings = DatabaseSettings.from_environment()
    engine = create_engine(settings)

    stores = pd.read_sql(
        text(
            """
            SELECT
                store_id,
                store_name,
                city,
                state,
                region,
                store_type,
                latitude,
                longitude
            FROM stores
            """
        ),
        engine,
    )

    weather = pd.read_sql(
        text(
            """
            SELECT
                date,
                store_id,
                temperature_2m_max_c,
                temperature_2m_min_c,
                precipitation_sum_mm,
                source
            FROM store_weather_daily
            """
        ),
        engine,
    )

    stores["store_id"] = (
        stores["store_id"]
        .astype("string")
        .str.strip()
    )

    weather["store_id"] = (
        weather["store_id"]
        .astype("string")
        .str.strip()
    )

    weather["order_date"] = pd.to_datetime(
        weather["date"],
        errors="raise",
    ).dt.strftime("%Y-%m-%d")

    weather = weather.drop(columns=["date"])

    gold = daily_sales.merge(
        stores,
        on="store_id",
        how="left",
        validate="many_to_one",
        indicator="_store_join",
    )

    missing_store_rows = int(
        gold["_store_join"].eq("left_only").sum()
    )

    gold = gold.drop(columns=["_store_join"])

    gold = gold.merge(
        weather,
        on=[
            "order_date",
            "store_id",
        ],
        how="left",
        validate="many_to_one",
        indicator="_weather_join",
    )

    missing_weather_rows = int(
        gold["_weather_join"].eq("left_only").sum()
    )

    gold = gold.drop(columns=["_weather_join"])

    missing_product_name_rows = int(
        gold["canonical_product_name"].isna().sum()
    )

    duplicate_grain_rows = int(
        gold.duplicated(
            subset=GRAIN_COLUMNS,
            keep=False,
        ).sum()
    )

    silver_units = float(orders["quantity"].sum())
    gold_units = float(gold["units_sold"].sum())

    silver_sales = round(
        float(orders["net_sales"].sum()),
        2,
    )

    gold_sales = round(
        float(gold["net_sales"].sum()),
        2,
    )

    units_difference = round(
        gold_units - silver_units,
        6,
    )

    net_sales_difference = round(
        gold_sales - silver_sales,
        2,
    )

    report = {
        "gold_table": GOLD_TABLE_NAME,
        "grain": GRAIN_COLUMNS,
        "silver_rows": int(len(orders)),
        "gold_rows": int(len(gold)),
        "duplicate_grain_rows": duplicate_grain_rows,
        "missing_store_rows": missing_store_rows,
        "missing_weather_rows": missing_weather_rows,
        "missing_product_name_rows": missing_product_name_rows,
        "silver_units": silver_units,
        "gold_units": gold_units,
        "units_difference": units_difference,
        "silver_net_sales": silver_sales,
        "gold_net_sales": gold_sales,
        "net_sales_difference": net_sales_difference,
        "sql_rows": None,
        "sql_csv_row_count_difference": None,
        "validation_passed": False,
    }

    prepublish_passed = all(
        [
            duplicate_grain_rows == 0,
            missing_store_rows == 0,
            missing_weather_rows == 0,
            missing_product_name_rows == 0,
            abs(units_difference) < 0.000001,
            abs(net_sales_difference) < 0.01,
        ]
    )

    if not prepublish_passed:
        write_validation_report(report)

        raise ValueError(
            "Gold validation failed before publishing. "
            f"See {GOLD_VALIDATION_PATH}"
        )

    output_columns = [
        "order_date",
        "store_id",
        "canonical_product_id",
        "canonical_product_name",
        "store_name",
        "city",
        "state",
        "region",
        "store_type",
        "latitude",
        "longitude",
        "order_count",
        "units_sold",
        "net_sales",
        "temperature_2m_max_c",
        "temperature_2m_min_c",
        "precipitation_sum_mm",
        "source",
    ]

    gold = (
        gold[output_columns]
        .sort_values(GRAIN_COLUMNS)
        .reset_index(drop=True)
    )

    GOLD_SALES_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    gold.to_csv(
        GOLD_SALES_PATH,
        index=False,
        lineterminator="\n",
    )

    gold.to_sql(
        GOLD_TABLE_NAME,
        engine,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=1000,
    )

    with engine.connect() as connection:
        sql_rows = connection.execute(
            text(
                f"SELECT COUNT(*) FROM {GOLD_TABLE_NAME}"
            )
        ).scalar_one()

    sql_rows = int(sql_rows)

    sql_csv_difference = (
        sql_rows - len(gold)
    )

    report["sql_rows"] = sql_rows
    report["sql_csv_row_count_difference"] = (
        sql_csv_difference
    )

    report["validation_passed"] = (
        sql_csv_difference == 0
    )

    write_validation_report(report)

    if not report["validation_passed"]:
        raise ValueError(
            "SQL and CSV row counts do not match."
        )

    print(
        "Gold sales complete:"
        f"\n  Silver order rows: {len(orders)}"
        f"\n  Gold rows: {len(gold)}"
        f"\n  Units: {gold_units}"
        f"\n  Net sales: {gold_sales:.2f}"
        f"\n  CSV: {GOLD_SALES_PATH}"
        f"\n  SQL table: {GOLD_TABLE_NAME}"
        f"\n  Validation: {GOLD_VALIDATION_PATH}"
    )

    return gold


if __name__ == "__main__":
    build_gold_sales()

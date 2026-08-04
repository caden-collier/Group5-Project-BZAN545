"""Validate the analytics-ready table and publish it to MariaDB."""

from __future__ import annotations

import json

import pandas as pd
from sqlalchemy import Date, String, text

from bzan545.config import DATA_DIR, DatabaseSettings
from bzan545.weather import create_engine


PROCESSED_DIR = DATA_DIR / "processed"

CLEAN_PATH = (
    PROCESSED_DIR
    / "order_lines_clean.csv"
)

CLEANING_SUMMARY_PATH = (
    PROCESSED_DIR
    / "order_cleaning_summary.json"
)

RECONCILED_PATH = (
    PROCESSED_DIR
    / "order_lines_reconciled.csv"
)

DAILY_PATH = (
    PROCESSED_DIR
    / "daily_sales.csv"
)

FINAL_PATH = (
    PROCESSED_DIR
    / "daily_sales_weather.csv"
)

VALIDATION_PATH = (
    PROCESSED_DIR
    / "daily_sales_validation.json"
)

PUBLISHED_PATH = (
    PROCESSED_DIR
    / "group5_rto_daily_sales_weather.csv"
)

SQL_TABLE = "group5_rto_daily_sales_weather"


GRAIN = [
    "order_date",
    "store_id",
    "canonical_product_id",
]


PUBLISH_COLUMN_ORDER = [
    "order_date",
    "store_id",
    "store_name",
    "city",
    "state",
    "latitude",
    "longitude",
    "canonical_product_id",
    "canonical_product_name",
    "canonical_category",
    "product_reconciliation_status",
    "order_count",
    "units_sold",
    "net_sales",
    "temperature_2m_max_c",
    "temperature_2m_min_c",
    "precipitation_sum_mm",
]


REQUIRED_PUBLISH_COLUMNS = {
    "order_date",
    "store_id",
    "latitude",
    "longitude",
    "canonical_product_id",
    "units_sold",
    "net_sales",
}


class SalesValidationError(RuntimeError):
    """Raised when the final table fails validation."""


def normalize_boolean(
    values: pd.Series,
) -> pd.Series:
    """Convert CSV boolean values to true booleans."""

    if values.dtype == bool:
        return values

    normalized = (
        values.astype(str)
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
        invalid = sorted(
            normalized[
                mapped.isna()
            ]
            .unique()
            .tolist()
        )

        raise SalesValidationError(
            "Could not interpret boolean "
            f"values: {invalid}"
        )

    return mapped.astype(bool)


def write_report(
    report: dict[str, object],
) -> None:
    """Write the validation report."""

    VALIDATION_PATH.write_text(
        json.dumps(
            report,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )


def validate_and_publish(
    engine=None,
) -> dict[str, object]:
    """Validate outputs and publish the final table."""

    cleaning_summary = json.loads(
        CLEANING_SUMMARY_PATH.read_text(
            encoding="utf-8"
        )
    )

    clean = pd.read_csv(
        CLEAN_PATH
    )

    reconciled = pd.read_csv(
        RECONCILED_PATH
    )

    daily = pd.read_csv(
        DAILY_PATH
    )

    final = pd.read_csv(
        FINAL_PATH
    )

    required_final_columns = {
        *GRAIN,
        "units_sold",
        "net_sales",
        "store_joined_flag",
        "weather_available_flag",
    }

    missing_columns = (
        required_final_columns
        - set(final.columns)
    )

    if missing_columns:
        raise SalesValidationError(
            "Final table is missing columns: "
            f"{sorted(missing_columns)}"
        )

    final["store_joined_flag"] = (
        normalize_boolean(
            final["store_joined_flag"]
        )
    )

    final["weather_available_flag"] = (
        normalize_boolean(
            final["weather_available_flag"]
        )
    )

    for frame, columns in [
        (
            clean,
            [
                "quantity",
                "unit_price",
            ],
        ),
        (
            daily,
            [
                "units_sold",
                "net_sales",
            ],
        ),
        (
            final,
            [
                "units_sold",
                "net_sales",
            ],
        ),
    ]:
        for column in columns:
            frame[column] = pd.to_numeric(
                frame[column],
                errors="raise",
            )

    source_units = float(
        clean["quantity"].sum()
    )

    final_units = float(
        final["units_sold"].sum()
    )

    # unit_price is already the actual
    # post-discount selling price.
    source_net_sales = float(
        (
            clean["quantity"]
            * clean["unit_price"]
        ).sum()
    )

    final_net_sales = float(
        final["net_sales"].sum()
    )

    report = {
        "table_name": SQL_TABLE,

        "grain": (
            "one row per order_date, store_id, "
            "and canonical_product_id"
        ),

        "source_file_count": int(
            cleaning_summary[
                "source_file_count"
            ]
        ),

        "source_date_count": int(
            cleaning_summary[
                "source_date_count"
            ]
        ),

        "raw_row_count": int(
            cleaning_summary[
                "raw_row_count"
            ]
        ),

        "exact_duplicate_rows_removed": int(
            cleaning_summary[
                "exact_duplicate_rows_removed"
            ]
        ),

        "missing_calendar_dates": (
            cleaning_summary[
                "missing_calendar_dates"
            ]
        ),

        "clean_order_line_count": int(
            len(clean)
        ),

        "clean_unique_order_id_count": int(
            clean["order_id"].nunique()
        ),

        "clean_duplicate_order_id_count": int(
            clean["order_id"]
            .duplicated()
            .sum()
        ),

        "reconciled_order_line_count": int(
            len(reconciled)
        ),

        "daily_sales_row_count": int(
            len(daily)
        ),

        "final_row_count": int(
            len(final)
        ),

        "duplicate_grain_rows": int(
            final
            .duplicated(GRAIN)
            .sum()
        ),

        "missing_store_rows": int(
            (
                ~final[
                    "store_joined_flag"
                ]
            ).sum()
        ),

        "missing_weather_rows": int(
            (
                ~final[
                    "weather_available_flag"
                ]
            ).sum()
        ),

        "source_units": source_units,

        "final_units": final_units,

        "units_difference": (
            final_units
            - source_units
        ),

        "source_net_sales": round(
            source_net_sales,
            2,
        ),

        "final_net_sales": round(
            final_net_sales,
            2,
        ),

        "net_sales_difference": round(
            final_net_sales
            - source_net_sales,
            2,
        ),

        "reconciliation_status_counts": {
            str(status): int(count)
            for status, count
            in reconciled[
                "product_reconciliation_status"
            ]
            .value_counts(
                dropna=False
            )
            .items()
        },
    }

    errors: list[str] = []

    if (
        report[
            "clean_duplicate_order_id_count"
        ]
        != 0
    ):
        errors.append(
            "clean order IDs are not unique"
        )

    if len(reconciled) != len(clean):
        errors.append(
            "product reconciliation changed "
            "the order-line count"
        )

    if len(final) != len(daily):
        errors.append(
            "store/weather enrichment changed "
            "the daily row count"
        )

    if report["duplicate_grain_rows"] != 0:
        errors.append(
            "the final grain is not unique"
        )

    if report["missing_store_rows"] != 0:
        errors.append(
            "some rows did not join to stores"
        )

    if report["missing_weather_rows"] != 0:
        errors.append(
            "some rows did not join to weather"
        )

    if (
        abs(
            float(
                report[
                    "units_difference"
                ]
            )
        )
        > 0.000001
    ):
        errors.append(
            "units changed during processing"
        )

    if (
        abs(
            float(
                report[
                    "net_sales_difference"
                ]
            )
        )
        > 0.01
    ):
        errors.append(
            "net sales changed during processing"
        )

    report[
        "validation_errors"
    ] = errors

    report[
        "validation_passed"
    ] = not errors

    write_report(
        report
    )

    if errors:
        raise SalesValidationError(
            "Validation failed: "
            + "; ".join(errors)
        )

    missing_publish_columns = (
        REQUIRED_PUBLISH_COLUMNS
        - set(final.columns)
    )

    if missing_publish_columns:
        raise SalesValidationError(
            "Cannot publish the curated table. "
            "Missing required columns: "
            f"{sorted(missing_publish_columns)}"
        )

    publish_columns = [
        column
        for column in PUBLISH_COLUMN_ORDER
        if column in final.columns
    ]

    final_for_sql = final[
        publish_columns
    ].copy()

    final_for_sql.to_csv(
        PUBLISHED_PATH,
        index=False,
    )

    report[
        "published_table_name"
    ] = SQL_TABLE

    report[
        "published_csv_path"
    ] = str(
        PUBLISHED_PATH
    )

    report[
        "published_column_count"
    ] = len(
        publish_columns
    )

    report[
        "published_columns"
    ] = publish_columns

    print(
        "Published columns:",
        publish_columns,
    )

    print(
        "Wrote curated CSV:",
        PUBLISHED_PATH,
    )

    final_for_sql["order_date"] = (
        pd.to_datetime(
            final_for_sql[
                "order_date"
            ],
            errors="raise",
        )
        .dt.date
    )

    final_for_sql["store_id"] = (
        final_for_sql[
            "store_id"
        ]
        .astype(str)
    )

    final_for_sql[
        "canonical_product_id"
    ] = (
        final_for_sql[
            "canonical_product_id"
        ]
        .astype(str)
    )

    database_engine = (
        engine
        or create_engine(
            DatabaseSettings.from_environment()
        )
    )

    final_for_sql.to_sql(
        SQL_TABLE,
        database_engine,
        if_exists="replace",
        index=False,
        chunksize=1000,
        method="multi",
        dtype={
            "order_date": Date(),
            "store_id": String(32),
            "canonical_product_id": String(64),
        },
    )

    with database_engine.begin() as connection:
        connection.execute(
            text(
                f"""
                ALTER TABLE `{SQL_TABLE}`
                ADD PRIMARY KEY (
                    order_date,
                    store_id,
                    canonical_product_id
                )
                """
            )
        )

    sql_row_count = int(
        pd.read_sql(
            f"""
            SELECT COUNT(*) AS row_count
            FROM `{SQL_TABLE}`
            """,
            database_engine,
        )
        .iloc[0][
            "row_count"
        ]
    )

    report[
        "sql_row_count"
    ] = sql_row_count

    report[
        "sql_csv_row_count_difference"
    ] = (
        sql_row_count
        - len(final_for_sql)
    )

    if sql_row_count != len(
        final_for_sql
    ):
        report[
            "validation_passed"
        ] = False

        report[
            "validation_errors"
        ] = [
            "SQL row count does not match "
            "the curated CSV row count"
        ]

        write_report(
            report
        )

        raise SalesValidationError(
            "SQL and CSV row counts "
            "do not match"
        )

    write_report(
        report
    )

    print(
        "Published SQL table:",
        SQL_TABLE,
    )

    print(
        json.dumps(
            report,
            indent=2,
            default=str,
        )
    )

    return report


if __name__ == "__main__":
    validate_and_publish()
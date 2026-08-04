"""Join daily sales to stores and cached daily weather."""

from __future__ import annotations

import pandas as pd

from bzan545.config import DATA_DIR, DatabaseSettings
from bzan545.weather import create_engine, sync_weather


INPUT_PATH = (
    DATA_DIR
    / "processed"
    / "daily_sales.csv"
)

OUTPUT_PATH = (
    DATA_DIR
    / "processed"
    / "daily_sales_weather.csv"
)

GRAIN = [
    "order_date",
    "store_id",
    "canonical_product_id",
]


class WeatherEnrichmentError(RuntimeError):
    """Raised when store or weather joins are unsafe."""


def enrich_daily_sales(
    engine=None,
    *,
    sync_missing: bool = True,
) -> pd.DataFrame:
    """Backfill weather and join stores and weather."""

    daily_sales = pd.read_csv(INPUT_PATH)

    daily_sales["order_date"] = (
        pd.to_datetime(
            daily_sales["order_date"],
            errors="raise",
        )
        .dt.date
    )

    daily_sales["store_id"] = (
        daily_sales["store_id"]
        .astype(str)
    )

    database_engine = (
        engine
        or create_engine(
            DatabaseSettings.from_environment()
        )
    )

    if sync_missing:
        order_dates = sorted(
            daily_sales["order_date"]
            .unique()
            .tolist()
        )

        for order_date in order_dates:
            print(
                f"Checking weather for {order_date}..."
            )

            sync_weather(
                str(order_date),
                engine=database_engine,
            )

    stores = pd.read_sql(
        "SELECT * FROM stores",
        database_engine,
    )

    weather = pd.read_sql(
        """
        SELECT *
        FROM store_weather_daily
        """,
        database_engine,
    )

    if "store_id" not in stores.columns:
        raise WeatherEnrichmentError(
            "stores is missing store_id"
        )

    required_weather_columns = {
        "store_id",
        "date",
    }

    missing_weather_columns = (
        required_weather_columns
        - set(weather.columns)
    )

    if missing_weather_columns:
        raise WeatherEnrichmentError(
            "store_weather_daily is missing "
            f"columns: {sorted(missing_weather_columns)}"
        )

    stores["store_id"] = (
        stores["store_id"]
        .astype(str)
    )

    weather["store_id"] = (
        weather["store_id"]
        .astype(str)
    )

    weather["date"] = (
        pd.to_datetime(
            weather["date"],
            errors="raise",
        )
        .dt.date
    )

    if stores["store_id"].duplicated().any():
        duplicate_store_ids = (
            stores.loc[
                stores["store_id"].duplicated(
                    keep=False
                ),
                "store_id",
            ]
            .unique()
            .tolist()
        )

        raise WeatherEnrichmentError(
            "stores contains duplicate "
            f"store IDs: {duplicate_store_ids}"
        )

    duplicate_weather = weather.duplicated(
        [
            "store_id",
            "date",
        ]
    )

    if duplicate_weather.any():
        raise WeatherEnrichmentError(
            "store_weather_daily contains "
            "duplicate store/date rows"
        )

    # Join store attributes.
    final_table = daily_sales.merge(
        stores,
        on="store_id",
        how="left",
        validate="many_to_one",
        indicator="_store_join",
    )

    final_table["store_joined_flag"] = (
        final_table["_store_join"]
        .eq("both")
    )

    final_table = final_table.drop(
        columns="_store_join"
    )

    # Align the weather date with order_date.
    weather = weather.rename(
        columns={
            "date": "order_date",
            "source": "weather_source",
        }
    )

    # Join daily weather at store/date grain.
    final_table = final_table.merge(
        weather,
        on=[
            "store_id",
            "order_date",
        ],
        how="left",
        validate="many_to_one",
        indicator="_weather_join",
    )

    final_table["weather_available_flag"] = (
        final_table["_weather_join"]
        .eq("both")
    )

    final_table = final_table.drop(
        columns="_weather_join"
    )

    final_table = (
        final_table
        .sort_values(GRAIN)
        .reset_index(drop=True)
    )

    final_table.to_csv(
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
        "Final rows:",
        len(final_table),
    )

    print(
        "Rows missing stores:",
        int(
            (
                ~final_table[
                    "store_joined_flag"
                ]
            ).sum()
        ),
    )

    print(
        "Rows missing weather:",
        int(
            (
                ~final_table[
                    "weather_available_flag"
                ]
            ).sum()
        ),
    )

    return final_table


if __name__ == "__main__":
    enrich_daily_sales()
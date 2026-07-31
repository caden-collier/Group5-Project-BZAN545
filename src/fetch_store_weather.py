import json
import time
import requests
import pandas as pd
import sqlalchemy


def create_mysql_utk_engine(
    database,
    username,
    password,
    host="mariadb-compx0.oit.utk.edu",
    port=3306,
):
    connection_string = sqlalchemy.URL.create(
        "mysql+pymysql",
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
    )
    return sqlalchemy.create_engine(connection_string)


with open("credentials.json") as file:
    credentials = json.load(file)

engine = create_mysql_utk_engine(
    database="ltk528_bzan545",
    username=credentials["username"],
    password=credentials["password"],
)


needed = pd.read_sql(
    "SELECT DISTINCT store_id, latitude, longitude, order_date FROM orders_with_stores_and_products;",
    engine,
)

needed["order_date"] = pd.to_datetime(needed["order_date"]).dt.date

try:
    existing = pd.read_sql(
        "SELECT store_id, date FROM store_weather_daily;",
        engine,
    )
except Exception:
    # Table doesn't exist yet on first run
    existing = pd.DataFrame(columns=["store_id", "date"])


existing["date"] = pd.to_datetime(existing["date"]).dt.date

to_fetch = needed.merge(
    existing,
    left_on=["store_id", "order_date"],
    right_on=["store_id", "date"],
    how="left",
    indicator=True,
).query("_merge == 'left_only'")[["store_id", "latitude", "longitude", "order_date"]]

print(f"{len(to_fetch)} store/date combinations need weather data "
      f"({len(needed) - len(to_fetch)} already cached).")


results = []

for store_id, group in to_fetch.groupby("store_id"):
    lat = group["latitude"].iloc[0]
    lon = group["longitude"].iloc[0]
    start_date = group["order_date"].min()
    end_date = group["order_date"].max()

    response = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "America/New_York",  # adjust to your stores' timezone
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    daily = pd.DataFrame(data["daily"])
    daily["store_id"] = store_id
    daily = daily.rename(columns={"time": "date"})
    daily["date"] = pd.to_datetime(daily["date"]).dt.date

    missing_dates = set(group["order_date"])
    daily = daily[daily["date"].isin(missing_dates)]

    results.append(daily)

    time.sleep(0.2)  # be polite to the free API :0



if results:
    new_weather = pd.concat(results, ignore_index=True)

    new_weather.to_sql(
        name="store_weather_daily",
        con=engine,
        if_exists="append",
        index=False,
    )

    print(f"Inserted {len(new_weather)} new rows into store_weather_daily.")
else:
    print("Nothing to fetch — all store/date combinations already cached.")

# Confirm
preview = pd.read_sql("SELECT * FROM store_weather_daily LIMIT 10;", engine)
print(preview)


orders_with_weather = pd.read_sql("SELECT * FROM orders_with_stores_and_products LEFT JOIN store_weather_daily ON orders_with_stores_and_products.store_id = store_weather_daily.store_id AND orders_with_stores_and_products.order_date = store_weather_daily.date", engine)
orders_with_weather


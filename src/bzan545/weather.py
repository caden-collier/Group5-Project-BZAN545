"""Fetch daily store weather from Open-Meteo and cache it in MariaDB."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Any

from .config import DatabaseSettings


WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_VARIABLES = (
    "temperature_2m_max", "temperature_2m_min", "precipitation_sum"
)


class WeatherError(RuntimeError):
    """Raised when weather data cannot be fetched or validated."""


@dataclass(frozen=True)
class Store:
    store_id: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class WeatherRow:
    store_id: str
    date: str
    temperature_2m_max_c: float | None
    temperature_2m_min_c: float | None
    precipitation_sum_mm: float | None
    source: str = "open-meteo"


def build_weather_url(store: Store, target_date: str) -> str:
    date.fromisoformat(target_date)
    query = urllib.parse.urlencode(
        {
            "latitude": store.latitude,
            "longitude": store.longitude,
            "start_date": target_date,
            "end_date": target_date,
            "daily": ",".join(DAILY_VARIABLES),
            "timezone": "auto",
        }
    )
    return f"{WEATHER_URL}?{query}"


def parse_weather_response(
    payload: dict[str, Any], store_id: str, target_date: str
) -> WeatherRow:
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise WeatherError("Open-Meteo response has no daily weather object.")
    dates = daily.get("time")
    if not isinstance(dates, list) or target_date not in dates:
        raise WeatherError(f"Open-Meteo returned no weather for {target_date}.")
    index = dates.index(target_date)

    def value(name: str) -> float | None:
        values = daily.get(name)
        if not isinstance(values, list) or index >= len(values):
            raise WeatherError(f"Open-Meteo response is missing {name}.")
        item = values[index]
        return None if item is None else float(item)

    return WeatherRow(
        store_id=store_id,
        date=target_date,
        temperature_2m_max_c=value("temperature_2m_max"),
        temperature_2m_min_c=value("temperature_2m_min"),
        precipitation_sum_mm=value("precipitation_sum"),
    )


def fetch_weather(
    store: Store, target_date: str, *, timeout_seconds: int = 30
) -> WeatherRow:
    request = urllib.request.Request(
        build_weather_url(store, target_date),
        headers={"User-Agent": "BZAN545-Daily-Pipeline/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read())
    except Exception as exc:
        raise WeatherError(
            f"Could not fetch weather for {store.store_id} on {target_date}: {exc}"
        ) from exc
    return parse_weather_response(payload, store.store_id, target_date)


def create_engine(settings: DatabaseSettings):
    """Create a SQLAlchemy engine without exposing the password in a URL string."""
    import sqlalchemy

    url = sqlalchemy.URL.create(
        "mysql+pymysql",
        username=settings.username,
        password=settings.password,
        host=settings.host,
        port=settings.port,
        database=settings.database,
    )
    return sqlalchemy.create_engine(url, pool_pre_ping=True)


def sync_weather(
    target_date: str,
    *,
    engine=None,
    settings: DatabaseSettings | None = None,
) -> int:
    """Cache one weather row per store for the ingested order date."""
    from sqlalchemy import text

    date.fromisoformat(target_date)
    database_engine = engine or create_engine(
        settings or DatabaseSettings.from_environment()
    )
    with database_engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS store_weather_daily (
                store_id VARCHAR(32) NOT NULL,
                date DATE NOT NULL,
                temperature_2m_max_c DECIMAL(8, 3) NULL,
                temperature_2m_min_c DECIMAL(8, 3) NULL,
                precipitation_sum_mm DECIMAL(10, 3) NULL,
                source VARCHAR(32) NOT NULL,
                PRIMARY KEY (store_id, date)
            )
        """))
        stores = [Store(str(row.store_id), float(row.latitude), float(row.longitude))
                  for row in connection.execute(text(
                      "SELECT store_id, latitude, longitude FROM stores "
                      "WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
                  ))]
        existing = {
            str(row.store_id)
            for row in connection.execute(
                text("SELECT store_id FROM store_weather_daily WHERE date = :date"),
                {"date": target_date},
            )
        }

    missing = [store for store in stores if store.store_id not in existing]
    rows = [fetch_weather(store, target_date) for store in missing]
    if rows:
        statement = text("""
            INSERT IGNORE INTO store_weather_daily (
                store_id, date, temperature_2m_max_c,
                temperature_2m_min_c, precipitation_sum_mm, source
            ) VALUES (
                :store_id, :date, :temperature_2m_max_c,
                :temperature_2m_min_c, :precipitation_sum_mm, :source
            )
        """)
        with database_engine.begin() as connection:
            connection.execute(statement, [row.__dict__ for row in rows])
    print(
        f"Weather sync complete for {target_date}: {len(rows)} inserted, "
        f"{len(existing)} already cached."
    )
    return len(rows)

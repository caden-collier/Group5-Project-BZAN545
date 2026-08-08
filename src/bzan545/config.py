"""Project paths and environment-based configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"
BRONZE_ORDERS_DIR = BRONZE_DIR / "orders"
INGESTION_LOG_PATH = BRONZE_DIR / "ingestion_log.csv"

PRODUCT_CROSSWALK_PATH = SILVER_DIR / "canonical_product_crosswalk.csv"
SILVER_ORDERS_PATH = SILVER_DIR / "order_lines.csv"
GOLD_SALES_PATH = GOLD_DIR / "group5_rto_daily_sales_weather.csv"
GOLD_VALIDATION_PATH = GOLD_DIR / "daily_sales_validation.json"


@dataclass(frozen=True)
class DatabaseSettings:
    """Connection settings loaded from environment variables."""

    username: str
    password: str
    database: str = "ltk528_bzan545"
    host: str = "mariadb-compx0.oit.utk.edu"
    port: int = 3306

    @classmethod
    def from_environment(cls) -> "DatabaseSettings":
        username = os.getenv("BZAN_DB_USERNAME", "")
        password = os.getenv("BZAN_DB_PASSWORD", "")
        if not username or not password:
            raise ValueError(
                "Set BZAN_DB_USERNAME and BZAN_DB_PASSWORD before syncing weather."
            )
        return cls(
            username=username,
            password=password,
            database=os.getenv("BZAN_DB_DATABASE", "ltk528_bzan545"),
            host=os.getenv("BZAN_DB_HOST", "mariadb-compx0.oit.utk.edu"),
            port=int(os.getenv("BZAN_DB_PORT", "3306")),
        )

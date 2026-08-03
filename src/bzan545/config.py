"""Project paths and environment-based configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_ORDERS_DIR = DATA_DIR / "raw" / "orders"
INGESTION_LOG_PATH = DATA_DIR / "logs" / "ingestion_log.csv"


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

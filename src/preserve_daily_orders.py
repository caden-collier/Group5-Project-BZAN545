import csv
import hashlib
import io
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# URL for the daily orders file
ORDERS_URL = "https://raw.githubusercontent.com/AdamSpannbauer/su26-bzan545-current-orders/refs/heads/master/orders.csv"

# Expected columns in the CSV
EXPECTED_COLUMNS = (
    "order_id",
    "order_date",
    "store_id",
    "product_id",
    "quantity",
    "unit_price",
    "discount_pct",
    "sales_channel",
    "loyalty_member",
)

# Where raw orders should be stored
RAW_ROOT = Path("data/raw/orders")


class PreservationError(Exception):
    """Raised when the daily orders file cannot be preserved safely."""


@dataclass
class ValidatedOrders:
    order_date: str
    row_count: int
    sha256: str
    file_size_bytes: int


def sha256_bytes(data: bytes) -> str:
    """Return SHA-256 hash of the raw bytes."""
    return hashlib.sha256(data).hexdigest()


def download_orders(url: str = ORDERS_URL) -> bytes:
    """Download the daily orders CSV as raw bytes."""
    try:
        with urllib.request.urlopen(url) as response:
            return response.read()
    except Exception as exc:
        raise PreservationError(f"Could not download orders file: {exc}")


def validate_orders_bytes(data: bytes) -> ValidatedOrders:
    """Validate the CSV: correct columns, at least one row, consistent date."""
    try:
        text = data.decode("utf-8")
    except Exception:
        raise PreservationError("File is not valid UTF-8 CSV.")

    reader = csv.DictReader(io.StringIO(text))

    # Check header
    if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
        raise PreservationError("Unexpected columns in orders.csv.")

    rows = list(reader)
    if not rows:
        raise PreservationError("CSV contains a header but no rows.")

    # Check that all rows have the same order_date
    dates = {row["order_date"] for row in rows}
    if len(dates) != 1:
        raise PreservationError("CSV must contain exactly one order_date.")

    order_date = next(iter(dates))

    return ValidatedOrders(
        order_date=order_date,
        row_count=len(rows),
        sha256=sha256_bytes(data),
        file_size_bytes=len(data),
    )


def preserve_orders_bytes(data: bytes) -> ValidatedOrders:
    """Save the validated daily orders file into data/raw/orders/<date>/."""
    facts = validate_orders_bytes(data)

    date_dir = RAW_ROOT / facts.order_date
    csv_path = date_dir / "orders.csv"

    # If already preserved, do nothing
    if csv_path.exists():
        return facts

    date_dir.mkdir(parents=True, exist_ok=True)
    csv_path.write_bytes(data)

    return facts

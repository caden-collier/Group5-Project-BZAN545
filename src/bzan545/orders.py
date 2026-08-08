"""Download, validate, hash, and preserve the daily orders CSV."""

from __future__ import annotations

import csv
import hashlib
import io
import tempfile
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TextIO

from .config import BRONZE_ORDERS_DIR


ORDERS_URL = (
    "https://raw.githubusercontent.com/AdamSpannbauer/"
    "su26-bzan545-current-orders/refs/heads/master/orders.csv"
)
PRODUCT_ID_COLUMNS = (
    "order_id", "order_date", "store_id", "product_id", "quantity",
    "unit_price", "discount_pct", "sales_channel", "loyalty_member",
)
NEW_PRODUCT_ID_COLUMNS = (
    "order_id", "order_date", "store_id", "new_product_id", "quantity",
    "unit_price", "discount_pct", "sales_channel", "loyalty_member",
)
ALLOWED_COLUMN_SETS = (PRODUCT_ID_COLUMNS, NEW_PRODUCT_ID_COLUMNS)
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024


class PreservationError(RuntimeError):
    """Raised when the orders file cannot be preserved safely."""


@dataclass(frozen=True)
class ValidatedOrders:
    order_date: str
    row_count: int
    sha256: str
    file_size_bytes: int
    product_id_column: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download_orders(url: str = ORDERS_URL, timeout_seconds: int = 30) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "BZAN545-Daily-Pipeline/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            data = response.read(MAX_DOWNLOAD_BYTES + 1)
    except Exception as exc:
        raise PreservationError(f"Could not download orders file: {exc}") from exc
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise PreservationError("Downloaded orders file exceeds the 20 MiB limit.")
    return data


def validate_orders_bytes(data: bytes) -> ValidatedOrders:
    """Validate the downloaded orders CSV before preserving it."""

    if not data:
        raise PreservationError("Downloaded orders file is empty.")

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PreservationError(
            "Orders file is not valid UTF-8 CSV."
        ) from exc

    if text.lstrip().lower().startswith(("<!doctype html", "<html")):
        raise PreservationError(
            "Downloaded content is HTML, not CSV."
        )

    reader = csv.DictReader(io.StringIO(text, newline=""))

    fieldnames = tuple(reader.fieldnames or ())
    actual_columns = set(fieldnames)

    legacy_columns = set(PRODUCT_ID_COLUMNS)
    new_columns = set(NEW_PRODUCT_ID_COLUMNS)

    if actual_columns == legacy_columns:
        product_id_column = "product_id"

    elif actual_columns == new_columns:
        product_id_column = "new_product_id"

    else:
        expected_columns = legacy_columns | new_columns

        missing = expected_columns - actual_columns
        extra = actual_columns - expected_columns

        message = []

        if missing:
            message.append(
                "Missing columns: "
                + ", ".join(sorted(missing))
            )

        if extra:
            message.append(
                "Unexpected columns: "
                + ", ".join(sorted(extra))
            )

        raise PreservationError("; ".join(message))

    rows = list(reader)

    if not rows:
        raise PreservationError(
            "Orders CSV contains a header but no rows."
        )

    order_dates: set[str] = set()

    for row_number, row in enumerate(rows, start=2):

        if None in row:
            raise PreservationError(
                f"Row {row_number} contains extra CSV fields."
            )

        if not (row.get("order_id") or "").strip():
            raise PreservationError(
                f"Row {row_number} has no order_id."
            )

        order_date = (row.get("order_date") or "").strip()

        try:
            date.fromisoformat(order_date)
        except ValueError as exc:
            raise PreservationError(
                f"Row {row_number} has an invalid order_date: {order_date!r}."
            ) from exc

        order_dates.add(order_date)

    if len(order_dates) != 1:
        raise PreservationError(
            "Orders CSV must contain exactly one order_date."
        )

    return ValidatedOrders(
        order_date=next(iter(order_dates)),
        row_count=len(rows),
        sha256=sha256_bytes(data),
        file_size_bytes=len(data),
        product_id_column=product_id_column,
    )


def preserve_orders_bytes(
    data: bytes,
    *,
    bronze_root: Path = BRONZE_ORDERS_DIR,
) -> ValidatedOrders:
    """Preserve validated bytes atomically without overwriting a prior capture."""
    facts = validate_orders_bytes(data)
    date_dir = bronze_root / facts.order_date
    csv_path = date_dir / "orders.csv"
    checksum_path = date_dir / "orders.csv.sha256"

    if csv_path.exists():
        existing_hash = sha256_bytes(csv_path.read_bytes())
        if existing_hash != facts.sha256:
            raise PreservationError(
                f"{csv_path} already has different contents; it was not overwritten."
            )
        if checksum_path.exists():
            recorded_hash = checksum_path.read_text(
                encoding="utf-8"
            ).split(maxsplit=1)[0]
            if recorded_hash.lower() != existing_hash:
                raise PreservationError(f"{checksum_path} does not match orders.csv.")
        return facts
    if date_dir.exists():
        raise PreservationError(
            f"{date_dir} exists without orders.csv; inspect it manually."
        )
    bronze_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{facts.order_date}.", dir=bronze_root
    ) as temp:
        staging_dir = Path(temp)
        (staging_dir / "orders.csv").write_bytes(data)
        (staging_dir / "orders.csv.sha256").write_text(
            f"{facts.sha256}  orders.csv\n", encoding="utf-8"
        )
        try:
            staging_dir.rename(date_dir)
        except OSError as exc:
            raise PreservationError(
                f"Could not preserve {facts.order_date} atomically: {exc}"
            ) from exc
    return facts


def inspect_orders(path: Path, *, output: TextIO | None = None) -> ValidatedOrders:
    """Validate a preserved file and print a human-friendly pandas profile."""
    import sys
    import pandas as pd

    data = path.read_bytes()
    facts = validate_orders_bytes(data)
    frame = pd.read_csv(path)
    stream = output or sys.stdout
    print(f"File: {path}", file=stream)
    print(f"Rows: {facts.row_count}", file=stream)
    print(f"Columns: {len(frame.columns)}", file=stream)
    print(f"Column names: {', '.join(frame.columns)}", file=stream)
    print(f"Order date: {facts.order_date}", file=stream)
    print(f"Product key: {facts.product_id_column}", file=stream)
    print(f"SHA-256: {facts.sha256}", file=stream)
    print(f"Missing values: {int(frame.isna().sum().sum())}", file=stream)
    print(
        f"Duplicate order IDs: {int(frame['order_id'].duplicated().sum())}",
        file=stream,
    )
    print(f"Unique stores: {frame['store_id'].nunique()}", file=stream)
    print(f"Unique products: {frame[facts.product_id_column].nunique()}", file=stream)
    print("First 5 records:", file=stream)
    print(frame.head().to_string(index=False), file=stream)
    return facts

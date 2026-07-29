"""Download, validate, hash, and preserve the current daily orders CSV."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import tempfile
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# Current course source for the daily orders file.
ORDERS_URL = (
    "https://raw.githubusercontent.com/AdamSpannbauer/"
    "su26-bzan545-current-orders/refs/heads/master/orders.csv"
)

# The product-system migration changed only the product key in daily orders.
# Accept both schemas so historical re-runs continue to work across the cutover.
PRODUCT_ID_COLUMNS = (
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
NEW_PRODUCT_ID_COLUMNS = (
    "order_id",
    "order_date",
    "store_id",
    "new_product_id",
    "quantity",
    "unit_price",
    "discount_pct",
    "sales_channel",
    "loyalty_member",
)
# The source changed product identifiers on 2026-07-28. Both exact schemas are
# present in the repository's preserved history and remain valid source data.
EXPECTED_COLUMNS = NEW_PRODUCT_ID_COLUMNS
ALLOWED_COLUMN_SETS = (PRODUCT_ID_COLUMNS, NEW_PRODUCT_ID_COLUMNS)

# Milestone 6 used these names. Keep the aliases so its migration code and
# documentation remain accurate after the automation improvements.
LEGACY_COLUMNS = PRODUCT_ID_COLUMNS
MIGRATED_COLUMNS = NEW_PRODUCT_ID_COLUMNS
ACCEPTED_COLUMNS = ALLOWED_COLUMN_SETS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = PROJECT_ROOT / "data" / "raw" / "orders"
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024


class PreservationError(RuntimeError):
    """Raised when the daily orders file cannot be preserved safely."""


@dataclass(frozen=True)
class ValidatedOrders:
    order_date: str
    row_count: int
    sha256: str
    file_size_bytes: int
    product_id_column: str


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase SHA-256 digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def download_orders(url: str = ORDERS_URL, timeout_seconds: int = 30) -> bytes:
    """Download the daily orders CSV as raw bytes."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "BZAN545-Daily-Orders-Preservation/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            data = response.read(MAX_DOWNLOAD_BYTES + 1)
    except Exception as exc:
        raise PreservationError(f"Could not download orders file: {exc}") from exc

    if len(data) > MAX_DOWNLOAD_BYTES:
        raise PreservationError(
            f"Downloaded file exceeds the {MAX_DOWNLOAD_BYTES}-byte safety limit."
        )
    return data


def validate_orders_bytes(data: bytes) -> ValidatedOrders:
    """Validate the CSV without modifying the downloaded bytes."""
    if not data:
        raise PreservationError("Downloaded file is empty.")

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PreservationError("File is not valid UTF-8 CSV.") from exc

    if text.lstrip().lower().startswith(("<!doctype html", "<html")):
        raise PreservationError("Downloaded file is HTML, not CSV.")

    reader = csv.DictReader(io.StringIO(text, newline=""))
    fieldnames = tuple(reader.fieldnames or ())
    if fieldnames not in ALLOWED_COLUMN_SETS:
        raise PreservationError("Unexpected columns in orders.csv.")

    rows = list(reader)
    if not rows:
        raise PreservationError("CSV contains a header but no rows.")

    order_dates: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        if None in row:
            raise PreservationError(f"Row {row_number} contains extra CSV fields.")
        if not (row.get("order_id") or "").strip():
            raise PreservationError(f"Row {row_number} has no order_id.")

        order_date = (row.get("order_date") or "").strip()
        try:
            date.fromisoformat(order_date)
        except ValueError as exc:
            raise PreservationError(
                f"Row {row_number} has an invalid order_date: {order_date!r}."
            ) from exc
        order_dates.add(order_date)

    if len(order_dates) != 1:
        raise PreservationError("CSV must contain exactly one order_date.")

    return ValidatedOrders(
        order_date=next(iter(order_dates)),
        row_count=len(rows),
        sha256=sha256_bytes(data),
        file_size_bytes=len(data),
        product_id_column=(
            "new_product_id"
            if fieldnames == NEW_PRODUCT_ID_COLUMNS
            else "product_id"
        ),
    )


def preserve_orders_bytes(
    data: bytes,
    *,
    raw_root: Path = RAW_ROOT,
    dry_run: bool = False,
) -> ValidatedOrders:
    """Preserve a validated file without overwriting an earlier daily capture."""
    facts = validate_orders_bytes(data)
    date_dir = raw_root / facts.order_date
    csv_path = date_dir / "orders.csv"
    checksum_path = date_dir / "orders.csv.sha256"

    if csv_path.exists():
        existing_hash = sha256_bytes(csv_path.read_bytes())
        if existing_hash != facts.sha256:
            raise PreservationError(
                f"{csv_path} already exists with different contents; "
                "the preserved file was not overwritten."
            )
        if checksum_path.exists():
            recorded_hash = checksum_path.read_text(
                encoding="utf-8"
            ).split(maxsplit=1)[0]
            if recorded_hash.lower() != existing_hash:
                raise PreservationError(
                    f"{checksum_path} does not match the preserved orders.csv."
                )
        return facts

    if date_dir.exists():
        raise PreservationError(
            f"{date_dir} exists without orders.csv; inspect it manually."
        )
    if dry_run:
        return facts

    raw_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{facts.order_date}.", dir=raw_root
    ) as temporary_directory:
        staging_dir = Path(temporary_directory)
        (staging_dir / "orders.csv").write_bytes(data)
        (staging_dir / "orders.csv.sha256").write_text(
            f"{facts.sha256}  orders.csv\n",
            encoding="utf-8",
        )
        try:
            staging_dir.rename(date_dir)
        except OSError as exc:
            raise PreservationError(
                f"Could not preserve {facts.order_date} without overwriting data: {exc}"
            ) from exc

    return facts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="download and validate without saving files",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
        help="download timeout in seconds (default: 30)",
    )
    args = parser.parse_args()

    try:
        data = download_orders(timeout_seconds=args.timeout_seconds)
        facts = preserve_orders_bytes(data, dry_run=args.dry_run)
    except PreservationError as exc:
        print(f"Ingestion failed: {exc}")
        return 1

    status = "Validated" if args.dry_run else "Preserved"
    print(f"{status} orders for {facts.order_date}.")
    print(f"Rows: {facts.row_count}")
    print(f"Bytes: {facts.file_size_bytes}")
    print(f"SHA-256: {facts.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

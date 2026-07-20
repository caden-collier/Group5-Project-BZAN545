"""Download, validate, hash, and preserve the current daily orders CSV."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import tempfile
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path


DEFAULT_SOURCE_URL = "https://tiny.utk.edu/RToutfitters/daily/orders.csv"
DEFAULT_ORDERS_ROOT = Path("data/raw/orders")
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
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


class PreservationError(RuntimeError):
    """Raised when a download cannot be preserved safely."""


@dataclass(frozen=True)
class ValidatedOrders:
    """Facts verified from an orders CSV."""

    order_date: str
    row_count: int
    column_count: int
    sha256: str
    file_size_bytes: int


@dataclass(frozen=True)
class PreservationResult:
    """Outcome of a preservation attempt."""

    status: str
    csv_path: Path
    facts: ValidatedOrders


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase SHA-256 digest for data."""
    return hashlib.sha256(data).hexdigest()


def validate_orders_bytes(data: bytes) -> ValidatedOrders:
    """Validate raw CSV bytes without modifying them."""
    if not data:
        raise PreservationError("The downloaded file is empty.")
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise PreservationError(
            f"The download exceeds the {MAX_DOWNLOAD_BYTES}-byte safety limit."
        )

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PreservationError("The download is not valid UTF-8 CSV data.") from exc

    if text.lstrip().lower().startswith(("<!doctype html", "<html")):
        raise PreservationError("The download appears to be an HTML page, not CSV.")

    reader = csv.DictReader(io.StringIO(text, newline=""))
    fieldnames = tuple(reader.fieldnames or ())
    if fieldnames != EXPECTED_COLUMNS:
        raise PreservationError(
            "Unexpected columns. "
            f"Expected {', '.join(EXPECTED_COLUMNS)}; "
            f"received {', '.join(fieldnames) or 'none'}."
        )

    rows = list(reader)
    if not rows:
        raise PreservationError("The CSV contains a header but no order rows.")

    order_dates: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        if None in row:
            raise PreservationError(f"Row {row_number} has extra CSV fields.")
        order_id = (row.get("order_id") or "").strip()
        order_date = (row.get("order_date") or "").strip()
        if not order_id:
            raise PreservationError(f"Row {row_number} has no order_id.")
        if not order_date:
            raise PreservationError(f"Row {row_number} has no order_date.")
        try:
            date.fromisoformat(order_date)
        except ValueError as exc:
            raise PreservationError(
                f"Row {row_number} has an invalid order_date: {order_date!r}."
            ) from exc
        order_dates.add(order_date)

    if len(order_dates) != 1:
        raise PreservationError(
            "The CSV must represent exactly one order date; "
            f"found {', '.join(sorted(order_dates))}."
        )

    return ValidatedOrders(
        order_date=next(iter(order_dates)),
        row_count=len(rows),
        column_count=len(fieldnames),
        sha256=sha256_bytes(data),
        file_size_bytes=len(data),
    )


def download_orders(source_url: str, timeout_seconds: int = 30) -> tuple[bytes, str]:
    """Download the source file and return its bytes and resolved URL."""
    request = urllib.request.Request(
        source_url,
        headers={"User-Agent": "BZAN545-Daily-Orders-Preservation/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            data = response.read(MAX_DOWNLOAD_BYTES + 1)
            resolved_url = response.geturl()
    except Exception as exc:
        raise PreservationError(f"Could not download {source_url}: {exc}") from exc

    if len(data) > MAX_DOWNLOAD_BYTES:
        raise PreservationError(
            f"The download exceeds the {MAX_DOWNLOAD_BYTES}-byte safety limit."
        )
    return data, resolved_url


def _verify_existing_checksum(checksum_path: Path, expected_hash: str) -> None:
    if not checksum_path.exists():
        return
    recorded_hash = checksum_path.read_text(encoding="utf-8").split(maxsplit=1)[0]
    if recorded_hash.lower() != expected_hash:
        raise PreservationError(
            f"{checksum_path} does not match the preserved orders.csv file."
        )


def preserve_orders_bytes(
    data: bytes,
    *,
    source_url: str,
    resolved_url: str,
    orders_root: Path = DEFAULT_ORDERS_ROOT,
    captured_at: datetime | None = None,
    dry_run: bool = False,
) -> PreservationResult:
    """Preserve validated bytes, refusing to overwrite a different daily file."""
    facts = validate_orders_bytes(data)
    date_directory = orders_root / facts.order_date
    csv_path = date_directory / "orders.csv"
    checksum_path = date_directory / "orders.csv.sha256"

    if csv_path.exists():
        existing_hash = sha256_bytes(csv_path.read_bytes())
        if existing_hash != facts.sha256:
            raise PreservationError(
                f"{csv_path} already exists with different contents. "
                "It was not overwritten."
            )
        _verify_existing_checksum(checksum_path, existing_hash)
        return PreservationResult("already_preserved", csv_path, facts)

    if date_directory.exists():
        raise PreservationError(
            f"{date_directory} exists without orders.csv. "
            "It was not changed; inspect the incomplete directory manually."
        )

    if dry_run:
        return PreservationResult("would_preserve", csv_path, facts)

    capture_time = captured_at or datetime.now(timezone.utc)
    if capture_time.tzinfo is None:
        raise PreservationError("captured_at must include a timezone.")
    capture_time_utc = capture_time.astimezone(timezone.utc).replace(microsecond=0)
    capture_time_text = capture_time_utc.isoformat().replace("+00:00", "Z")

    checksum_text = f"{facts.sha256}  orders.csv\n"
    metadata = {
        "source_url": source_url,
        "resolved_url": resolved_url,
        "captured_at_utc": capture_time_text,
        "order_date": facts.order_date,
        "row_count": facts.row_count,
        "column_count": facts.column_count,
        "file_size_bytes": facts.file_size_bytes,
        "sha256": facts.sha256,
    }

    orders_root.mkdir(parents=True, exist_ok=True)
    staging_directory = Path(
        tempfile.mkdtemp(prefix=f".{facts.order_date}.", dir=orders_root)
    )
    try:
        (staging_directory / "orders.csv").write_bytes(data)
        (staging_directory / "orders.csv.sha256").write_text(
            checksum_text, encoding="utf-8"
        )
        (staging_directory / "capture.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        try:
            staging_directory.rename(date_directory)
        except OSError as exc:
            if date_directory.exists():
                raise PreservationError(
                    f"{date_directory} appeared during preservation. "
                    "Nothing was overwritten."
                ) from exc
            raise
    finally:
        if staging_directory.exists():
            shutil.rmtree(staging_directory)

    return PreservationResult("preserved", csv_path, facts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-url",
        default=DEFAULT_SOURCE_URL,
        help=f"CSV source URL (default: {DEFAULT_SOURCE_URL})",
    )
    parser.add_argument(
        "--orders-root",
        type=Path,
        default=DEFAULT_ORDERS_ROOT,
        help=f"storage root (default: {DEFAULT_ORDERS_ROOT.as_posix()})",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
        help="download timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="download and validate without writing files",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        data, resolved_url = download_orders(
            args.source_url, timeout_seconds=args.timeout_seconds
        )
        result = preserve_orders_bytes(
            data,
            source_url=args.source_url,
            resolved_url=resolved_url,
            orders_root=args.orders_root,
            dry_run=args.dry_run,
        )
    except PreservationError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Status: {result.status}")
    print(f"File: {result.csv_path.as_posix()}")
    print(f"Order date: {result.facts.order_date}")
    print(f"Rows: {result.facts.row_count}")
    print(f"Columns: {result.facts.column_count}")
    print(f"Bytes: {result.facts.file_size_bytes}")
    print(f"SHA-256: {result.facts.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

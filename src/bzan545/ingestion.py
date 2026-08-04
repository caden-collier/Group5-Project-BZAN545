"""Run orders ingestion and maintain its idempotent audit log."""

from __future__ import annotations

import csv
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import BRONZE_ORDERS_DIR, INGESTION_LOG_PATH
from .orders import (
    PreservationError,
    ValidatedOrders,
    download_orders,
    preserve_orders_bytes,
)


LOG_FIELDS = (
    "timestamp_utc", "order_date", "status", "row_count", "file_size_bytes",
    "sha256", "error_message", "sort_date",
)


@dataclass(frozen=True)
class IngestionResult:
    succeeded: bool
    facts: ValidatedOrders | None = None
    error_message: str = ""


def _event_key(row: dict[str, str]) -> tuple[str, str, str]:
    if row["status"] == "success":
        return ("success", row["order_date"], row["sha256"])
    return ("failure", row["sort_date"], row["error_message"])


def append_log_if_missing(
    row: dict[str, str], *, log_path: Path = INGESTION_LOG_PATH
) -> bool:
    """Append an event unless the same success or daily failure is already logged."""
    normalized_row = {field: row.get(field, "") for field in LOG_FIELDS}
    if log_path.exists():
        with log_path.open(newline="", encoding="utf-8-sig") as log_file:
            for existing in csv.DictReader(log_file):
                normalized = {field: existing.get(field) or "" for field in LOG_FIELDS}
                if _event_key(normalized) == _event_key(normalized_row):
                    return False
    log_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not log_path.exists() or log_path.stat().st_size == 0
    with log_path.open("a", newline="", encoding="utf-8") as log_file:
        writer = csv.DictWriter(log_file, fieldnames=LOG_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(normalized_row)
    return True


def run_ingestion(
    *,
    log_path: Path = INGESTION_LOG_PATH,
    bronze_root: Path = BRONZE_ORDERS_DIR,
    downloader: Callable[[], bytes] = download_orders,
    now: Callable[[], datetime] | None = None,
) -> IngestionResult:
    current_time = now() if now else datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    timestamp = current_time.astimezone(timezone.utc).isoformat()
    run_date = current_time.astimezone(timezone.utc).date().isoformat()

    try:
        facts = preserve_orders_bytes(downloader(), bronze_root=bronze_root)
    except PreservationError as exc:
        message = str(exc)
        added = append_log_if_missing(
            {
                "timestamp_utc": timestamp, "order_date": "", "status": "failure",
                "row_count": "", "file_size_bytes": "", "sha256": "",
                "error_message": message, "sort_date": run_date,
            },
            log_path=log_path,
        )
        print(f"Orders ingestion failed: {message}")
        print("Failure logged." if added else "Matching failure was already logged.")
        return IngestionResult(False, error_message=message)

    added = append_log_if_missing(
        {
            "timestamp_utc": timestamp, "order_date": facts.order_date,
            "status": "success", "row_count": str(facts.row_count),
            "file_size_bytes": str(facts.file_size_bytes), "sha256": facts.sha256,
            "error_message": "", "sort_date": facts.order_date,
        },
        log_path=log_path,
    )
    print(
        f"Orders ingestion succeeded for {facts.order_date}: "
        f"{facts.row_count} rows, {facts.product_id_column}."
    )
    print("Success logged." if added else "Matching success was already logged.")
    return IngestionResult(True, facts=facts)


def replay_raw_ingestions(
    *,
    bronze_root: Path = BRONZE_ORDERS_DIR,
    log_path: Path = INGESTION_LOG_PATH,
) -> tuple[int, int]:
    """Validate existing captures and add only missing audit-log events."""
    successes = failures = 0
    for csv_path in sorted(bronze_root.glob("*/orders.csv")):
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            facts = preserve_orders_bytes(
                csv_path.read_bytes(), bronze_root=bronze_root
            )
            if facts.order_date != csv_path.parent.name:
                raise PreservationError(
                    f"Folder {csv_path.parent.name} contains orders for "
                    f"{facts.order_date}."
                )
        except PreservationError as exc:
            failures += 1
            append_log_if_missing(
                {
                    "timestamp_utc": timestamp, "order_date": "", "status": "failure",
                    "row_count": "", "file_size_bytes": "", "sha256": "",
                    "error_message": str(exc), "sort_date": csv_path.parent.name,
                },
                log_path=log_path,
            )
            continue
        successes += 1
        append_log_if_missing(
            {
                "timestamp_utc": timestamp, "order_date": facts.order_date,
                "status": "success", "row_count": str(facts.row_count),
                "file_size_bytes": str(facts.file_size_bytes), "sha256": facts.sha256,
                "error_message": "", "sort_date": facts.order_date,
            },
            log_path=log_path,
        )
    print(f"Replay complete: {successes} valid, {failures} failed validation.")
    return successes, failures

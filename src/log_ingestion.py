import csv
from datetime import datetime, timezone
from pathlib import Path

from preserve_daily_orders import (
    download_orders,
    preserve_orders_bytes,
    PreservationError,
)

LOG_PATH = Path("data/logs/ingestion_log.csv")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

def process_orders_bytes(orders_bytes):
    """Decode, validate, and extract facts from raw CSV bytes."""
    try:
        facts = preserve_orders_bytes(orders_bytes)
        return facts
    except PreservationError as exc:
        raise exc


def ingest_from_raw(path):
    """Replay ingestion using an already-downloaded raw file."""
    with open(path, "rb") as f:
        orders_bytes = f.read()
    return process_orders_bytes(orders_bytes)


def append_log(row):
    """Append a row to the ingestion log CSV."""
    print("Writing to:", LOG_PATH.resolve())
    file_exists = LOG_PATH.exists()

    # Back to normal CSV behavior (no forced quotes)
    with LOG_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)

        if not file_exists:
            writer.writerow([
                "timestamp_utc",
                "order_date",
                "status",
                "row_count",
                "file_size_bytes",
                "sha256",
                "error_message",
                "sort_date",
            ])

        writer.writerow(row)


def run_ingestion():
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        data = download_orders()
        facts = preserve_orders_bytes(data)

        append_log([
            timestamp,
            facts.order_date,
            "success",
            facts.row_count,
            facts.file_size_bytes,
            facts.sha256,
            "",
            "",  # sort_date left blank intentionally
        ])

        print("Ingestion successful.")
        print(f"Order date: {facts.order_date}")
        print(f"Rows: {facts.row_count}")
        print(f"Bytes: {facts.file_size_bytes}")
        print(f"SHA-256: {facts.sha256}")

    except PreservationError as exc:
        append_log([
            timestamp,
            "",
            "failure",
            "",
            "",
            "",
            str(exc),
            "",  # sort_date left blank intentionally
        ])

        print("Ingestion failed.")
        print(f"Error: {exc}")


if __name__ == "__main__":
    run_ingestion()

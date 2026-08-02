import os
from log_ingestion import ingest_from_raw, append_log
from datetime import datetime, timezone
from preserve_daily_orders import PreservationError

RAW_DIR = r"C:\BZAN 545 Non Onedrive\Group 5 Final Project\Group5-Project-BZAN545\data\raw\orders"
TARGET_DATE = "2026-08-01"   # <--- just change this when needed

def main():
    csv_path = os.path.join(RAW_DIR, TARGET_DATE, "orders.csv")

    if not os.path.exists(csv_path):
        print(f"No raw file found for {TARGET_DATE}")
        return

    print(f"Manually ingesting {TARGET_DATE}...")

    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        facts = ingest_from_raw(csv_path)
        append_log([
            timestamp,
            facts.order_date,
            "success",
            facts.row_count,
            facts.file_size_bytes,
            facts.sha256,
            "",
        ])
        print(f"Ingestion successful for {TARGET_DATE}.")
    except PreservationError as exc:
        append_log([
            timestamp,
            TARGET_DATE,
            "failure",
            "",
            "",
            "",
            str(exc),
        ])
        print("Ingestion failed:", exc)

if __name__ == "__main__":
    main()

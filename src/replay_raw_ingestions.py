import os
from log_ingestion import ingest_from_raw, append_log
from datetime import datetime, timezone
from preserve_daily_orders import PreservationError

RAW_DIR = "C:\\BZAN 545 Non Onedrive\\Group 5 Final Project\\Group5-Project-BZAN545\\data\\raw\\orders"

def main():
    for date_folder in sorted(os.listdir(RAW_DIR)):
        if date_folder == "2026-07-28":
            continue

        csv_path = os.path.join(RAW_DIR, date_folder, "orders.csv")
        if os.path.exists(csv_path):
            print(f"Replaying ingestion for {date_folder}...")

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
            except PreservationError as exc:
                append_log([
                    timestamp,
                    date_folder,
                    "failure",
                    "",
                    "",
                    "",
                    str(exc),
                ])
                print("Failure logged:", exc)

if __name__ == "__main__":
    main()

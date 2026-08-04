# Data layers

```text
bronze/
  ingestion_log.csv       One row per logged ingestion event
  orders/YYYY-MM-DD/       Exact daily source files and checksums
  products/YYYY-MM-DD/     Exact product-table snapshots and checksums

silver/
  product_crosswalk.csv    Proposed old-to-new product mappings
  product_crosswalk_summary.json

gold/
  README.md                Placeholder for final analytics outputs
```

Bronze files are source evidence and must not be edited in place. Silver files
may be rebuilt from bronze data. Gold files must be analysis-ready and should be
derived from silver data rather than directly from a source capture.

The ingestion log's `timestamp_utc` is the time the event was written. For a
replay event, it is therefore the replay time; `order_date` remains the business
date contained in the source file.

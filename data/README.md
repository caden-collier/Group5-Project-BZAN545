# Data layers

```text
bronze/
  ingestion_log.csv       One row per logged ingestion event
  orders/YYYY-MM-DD/       Exact daily source files and checksums
  products/YYYY-MM-DD/     Exact product-table snapshots and checksums

silver/
  product_crosswalk.csv    Proposed new-to-legacy match candidates
  product_crosswalk_summary.json
  canonical_product_crosswalk.csv
                            Approved legacy-to-canonical mappings
  order_lines.csv           Cleaned orders with canonical product details

gold/
  group5_rto_daily_sales_weather.csv
                            Daily product/store sales with weather
  daily_sales_validation.json
                            Grain, join, reconciliation, and SQL checks
```

Bronze files are source evidence and must not be edited in place. Silver files
may be rebuilt from bronze data. Gold files must be analysis-ready and should be
derived from silver data rather than directly from a source capture.

The ingestion log's `timestamp_utc` is the time the event was written. For a
replay event, it is therefore the replay time; `order_date` remains the business
date contained in the source file.

## Product reconciliation policy

`product_crosswalk.csv` is a review aid, not the mapping used directly by the
dashboard pipeline. It proposes the best legacy match for every migrated
product using name, brand, and price similarity. Exact normalized-name matches
are identified automatically; non-exact matches and repeated legacy candidates
are marked `review_required` for a human decision.

`canonical_product_crosswalk.csv` contains the approved production mappings.
It maps legacy product IDs to canonical migrated IDs. New order files already
use canonical IDs, including products with no legacy predecessor. Legacy
products without an approved replacement retain their original ID so their
sales are not lost.

## Silver orders

`data/silver/order_lines.csv` contains one row per cleaned order.

It combines the preserved bronze order files, removes exact duplicate rows,
reconciles old and new product identifiers, and assigns canonical product
names, brands, categories, and subcategories. Product attributes come from the
newest complete bronze product snapshot. An order whose product is absent from
the snapshot is retained with explicit `Unknown` attributes rather than being
dropped.

## Gold daily sales

`data/gold/group5_rto_daily_sales_weather.csv` is the final
analytics-ready table.

Its grain is one row per `order_date`, `store_id`, and
`canonical_product_id`.

It contains aggregated sales, store information, and daily weather.

Validation results are stored in
`data/gold/daily_sales_validation.json`.

The validation report checks grain uniqueness, store and weather joins,
product completeness, preservation of units and net sales, and agreement
between the published CSV and MariaDB row counts. A failed prepublication check
stops the build.

## Current limitations and data coverage

- Daily bronze ingestion is scheduled independently from the database build.
  Silver, gold, cached weather, and SQL publishing are refreshed only when the
  UTK database workflow is started on a self-hosted runner connected to the UTK
  network or VPN.
- The current validated silver and gold files include orders through
  `2026-08-09`. Within the `2026-07-12` through `2026-08-09` range, no order
  capture exists for `2026-07-13`, `2026-07-24`, `2026-07-25`, `2026-08-03`,
  `2026-08-06`, or `2026-08-08`.
- Product attributes currently come from the newest complete product snapshot,
  dated `2026-07-29`. A newer product master must be captured before later
  product attributes can appear in rebuilt silver and gold outputs.
- Gold publishing replaces the MariaDB table on each validated rebuild rather
  than updating it incrementally. This is reasonable for the current project
  size but may need to change if the dataset grows substantially.

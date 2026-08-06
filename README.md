# Group 5 BZAN 545 data pipeline

This project captures daily orders, records each ingestion attempt, and adds
store-level weather data. The repository uses a simple bronze, silver, and gold
layout so it is clear how far each dataset has moved from its source.

## Project layout

```text
.github/workflows/        Scheduled GitHub Actions workflow
data/bronze/              Source captures and ingestion history
data/silver/              Cleaned or reconciled datasets
data/gold/                Final analysis-ready datasets
src/bzan545/              Active pipeline code
tests/                    Focused automated checks
docs/milestones/          Historical coursework
```

The three data layers have intentionally simple meanings:

- **Bronze:** preserve the source exactly as received. Daily order files and
  product snapshots are never silently overwritten.
- **Silver:** standardize or reconcile source data while retaining detail. The
  current product crosswalk belongs here because it maps the old and new
  product systems and exposes uncertain matches for review.
- **Gold:** publish the final tables used for reporting or analysis. This folder
  is reserved for the later analytics milestone; it is not populated early
  with duplicate intermediate files.

See `data/README.md` for the exact contents and rules of each layer.

## Install and run

Python 3.11 or newer is supported.

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
bzan545 ingest
```

The full daily pipeline needs database credentials:

```powershell
$env:BZAN_DB_USERNAME = "your NetID"
$env:BZAN_DB_PASSWORD = "your database password"
bzan545 daily
```

Useful commands:

- `bzan545 daily` ingests orders, writes the audit event, and syncs weather.
- `bzan545 daily --skip-weather` runs only orders ingestion and logging.
- `bzan545 inspect PATH` validates a bronze CSV and prints a pandas profile for
  human review.
- `bzan545 replay` validates preserved bronze captures and backfills missing log
  entries. Its timestamp is when replay logged the file, not its order date.
- `bzan545 crosswalk` rebuilds the silver product crosswalk from bronze product
  snapshots.
- `bzan545 weather YYYY-MM-DD` syncs weather for one date.

## What the order checks do

Order validation rejects empty or HTML downloads, unexpected columns, missing
order IDs, invalid dates, multiple dates in one file, and conflicting files for
an already-preserved date. A SHA-256 checksum verifies file identity and
integrity. It does **not** prove that the publisher supplied a fresh business
date.

`bzan545 inspect` runs those same content checks and then shows missing values,
duplicate order IDs, unique stores, unique products, and sample rows. Inspection
is read-only. Preservation adds the separate no-overwrite and checksum checks.

## Automation and weather

The workflow runs at 12:17 PM Eastern with a 1:17 PM retry. Each run makes up
to three ingestion attempts, five minutes apart, because the current-orders
file can briefly be unavailable while the daily version is published.
GitHub-hosted runners run the tests, execute `bzan545 daily --skip-weather`,
and commit changes under `data/bronze/orders/` and
`data/bronze/ingestion_log.csv`.
Weather is skipped because UTK MariaDB is not reachable from GitHub's network.

Run weather synchronization from a machine connected to the UTK network or VPN:

```powershell
$env:BZAN_DB_USERNAME = "your NetID"
$env:BZAN_DB_PASSWORD = "your database password"
bzan545 weather YYYY-MM-DD
```

Weather comes from Open-Meteo and is stored in MariaDB table
`store_weather_daily`, with one row per store and date. Temperatures are Celsius
and precipitation is millimeters.

## Product crosswalk verification

The crosswalk first accepts normalized product-name matches. Every other product
is ranked using only name similarity (70%), brand similarity (20%), and price
closeness (10%), and is marked `review_required`. A repeated legacy candidate is
also marked for review.

The tests check the matching rules with small examples and verify that every
real migrated product appears exactly once in the silver crosswalk, proposed
legacy IDs exist, and scores are valid. A test cannot establish the business
correctness of a proposed mapping, so uncertain matches remain a human decision.

## Analytics-ready daily sales table

The final analytics-ready table is named
`group5_rto_daily_sales_weather`.

### Grain

One row represents the daily sales for one canonical product at
one store:

- `order_date`
- `store_id`
- `canonical_product_id`

### Contents

The table includes:

- canonical product ID and product name
- store name and location information
- distinct order count
- units sold
- net sales
- daily maximum temperature
- daily minimum temperature
- daily precipitation

Store information is joined using `store_id`.

Weather is joined using `store_id` and `order_date`.

### Product reconciliation

Legacy products retain their original product IDs.

New products with exact crosswalk matches use the proposed legacy
product ID.

Products requiring review remain separate using a `NEW:` prefix.

Products missing from the product master remain separate using an
`UNMAPPED:` prefix.

### Outputs

- `data/silver/order_lines.csv`
- `data/gold/group5_rto_daily_sales_weather.csv`
- `data/gold/daily_sales_validation.json`
- MariaDB table `group5_rto_daily_sales_weather`

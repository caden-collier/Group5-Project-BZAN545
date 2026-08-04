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
tools/                    One-off migration and reporting scripts
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

The workflow runs at 10:37 PM Eastern with an 11:37 PM retry. It runs the tests,
executes `bzan545 daily`, and commits changes under `data/bronze/orders/` and
`data/bronze/ingestion_log.csv`.

Database credentials are stored as GitHub Actions secrets. Weather comes from
Open-Meteo and is stored in MariaDB table `store_weather_daily`, with one row per
store and date. Temperatures are Celsius and precipitation is millimeters.

## Product crosswalk verification

The matching-rule unit tests use small controlled examples. A separate
real-data test checks that every product in the bronze migrated-product snapshot
appears exactly once in the silver crosswalk, that proposed legacy IDs exist,
and that scores are valid. Ambiguous matches still require human review; a test
cannot establish the business correctness of a proposed mapping.

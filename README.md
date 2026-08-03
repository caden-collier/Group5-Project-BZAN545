# Group 5 BZAN 545 data pipeline

This repository automates the group's daily orders capture and store-weather
enrichment. One command downloads and validates orders, preserves the exact raw
file and checksum, records the outcome in an ingestion audit log, and caches
daily weather for every store in MariaDB.

## Project layout

```text
.github/workflows/       Scheduled GitHub Actions automation
data/raw/orders/         Immutable source captures by order date
data/logs/               Ingestion audit history
docs/                    Project guides and milestone documentation
src/bzan545/             Installable pipeline package
tests/                   Offline unit and integration-boundary tests
tools/                   One-off document-generation utilities
```

Historical coursework is retained in `docs/milestones/`. Active daily-pipeline
code lives in `src/bzan545/`; supporting migration utilities remain in `src/`.

## Local setup and commands

Python 3.11 or newer is supported.

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
bzan545 ingest
```

The complete pipeline also needs database credentials:

```powershell
$env:BZAN_DB_USERNAME = "your NetID"
$env:BZAN_DB_PASSWORD = "your database password"
bzan545 daily
```

Useful commands:

- `bzan545 daily` runs orders ingestion, logging, and weather synchronization.
- `bzan545 daily --skip-weather` runs only orders ingestion and logging.
- `bzan545 weather 2026-07-31` syncs weather for one order date.
- `bzan545 inspect path/to/orders.csv` validates and summarizes a raw capture.
- `bzan545 replay` safely backfills missing log events from preserved captures.

## GitHub Actions configuration

The workflow runs at 10:37 PM Eastern with an 11:37 PM retry. Add these GitHub
Actions repository secrets before enabling it:

- `BZAN_DB_USERNAME`
- `BZAN_DB_PASSWORD`

Optional repository variables are `BZAN_DB_DATABASE` and `BZAN_DB_HOST`; the
defaults are already set for the group's UTK database. The workflow always tries
to commit a success or failure ingestion-log event, even when a later stage
fails. Repeated runs are safe: raw files are never overwritten, log events are
deduplicated, and weather uses one database row per store and date.

Weather comes from Open-Meteo's Historical Weather API. Temperatures are stored
in Celsius and precipitation in millimeters in `store_weather_daily`.

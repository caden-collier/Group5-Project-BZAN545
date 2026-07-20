# Daily Orders Automation Guide

## What this automation does

GitHub downloads the official current orders CSV late each evening. It checks
the file before preserving it and stores each order date in its own folder:

```text
data/raw/orders/YYYY-MM-DD/
├── orders.csv
├── orders.csv.sha256
└── capture.json
```

The automation never submits anything to Canvas and never merges data into
`main`. It writes to the `daily-orders` review branch.

## What each file means

- `orders.csv` is the untouched file downloaded from the official source.
- `orders.csv.sha256` is the SHA-256 fingerprint of that exact file.
- `capture.json` records the source, capture time, represented order date, row
  and column counts, file size, and SHA-256 fingerprint.

Changing even one byte in `orders.csv` changes its SHA-256 fingerprint.

## Safety rules

The program preserves a download only when all of these checks pass:

- The download is not empty or an HTML error page.
- The CSV has the nine expected columns in the expected order.
- The CSV contains at least one order.
- Every record has an order ID and a valid `YYYY-MM-DD` order date.
- Every record represents the same date.

If a file for that date already exists:

- An identical SHA-256 fingerprint means the date is already preserved, so the
  program makes no changes.
- A different fingerprint causes the run to fail. The existing file is never
  overwritten.

## Schedule

GitHub Actions uses UTC. During Eastern Daylight Time, the two scheduled
attempts are approximately 10:30 PM and 11:30 PM Eastern. GitHub may start a
scheduled run a little late.

The second attempt is a backup. It normally finds the same already-preserved
file and makes no additional commit.

Scheduled workflows run from the repository's default branch. The automation
does not become scheduled merely because it exists on a draft branch.

## Required activation steps

Do these only after the group approves the automation:

1. Merge the approved Milestone 2 work, including the workflow, into `main`.
2. Create a branch named `daily-orders` from that updated `main`.
3. Push `daily-orders` to GitHub.
4. Open a pull request from `daily-orders` into `main`.
5. Keep that pull request open while daily collection continues.

New captures will appear as commits in the open pull request. Group members
still decide whether and when to merge them.

## Checking a run

On GitHub:

1. Open the repository.
2. Select **Actions**.
3. Select **Preserve daily orders**.
4. Open the most recent run.

A green check means the run completed. A red X means it stopped without
committing questionable data. Open the failed step to read the explanation.

## Running it manually

After the workflow is approved and present on `main`:

1. Open **Actions** on GitHub.
2. Select **Preserve daily orders**.
3. Select **Run workflow**.
4. Confirm the run.

Running it repeatedly is safe. An already-preserved identical file causes no
new commit.

## Running a safe local preview

From the project folder:

```text
python src/preserve_daily_orders.py --dry-run
```

This downloads and validates the current source but does not write a file.

To run the automated safety tests:

```text
python -m unittest discover -s tests -v
```

## Verifying a SHA-256 fingerprint

In PowerShell:

```text
Get-FileHash -Algorithm SHA256 data\raw\orders\YYYY-MM-DD\orders.csv
```

In Git Bash:

```text
sha256sum data/raw/orders/YYYY-MM-DD/orders.csv
```

The calculated value should match the value in `orders.csv.sha256`.

## If a run reports different contents for an existing date

Do not delete or replace the existing raw file. Compare the new source with the
preserved copy and ask the group or professor which version should be kept.
The automation intentionally stops rather than making that decision.

## What the automation cannot do

It cannot recover a missed date after the source has replaced that day's file.
It also cannot prove that the provider's original data was correct. SHA-256
shows whether the preserved copy has changed; it is not encryption and does
not recreate missing data.

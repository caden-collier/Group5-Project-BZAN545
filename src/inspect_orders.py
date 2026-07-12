"""Inspect a preserved raw orders CSV without modifying it."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


DEFAULT_ORDERS_PATH = Path("data/raw/orders/2026-07-12/orders.csv")


def inspect_orders(path: Path) -> None:
    """Print basic evidence that the raw orders file is readable."""
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)

    if not reader.fieldnames:
        raise ValueError(f"No header row found in {path}")

    order_dates = sorted(
        {row["order_date"] for row in rows if row.get("order_date")}
    )

    print(f"File: {path.as_posix()}")
    print(f"Rows: {len(rows)}")
    print(f"Columns: {len(reader.fieldnames)}")
    print(f"Column names: {', '.join(reader.fieldnames)}")
    print(f"Order dates: {', '.join(order_dates)}")
    print("First 3 records:")
    for row in rows[:3]:
        print(row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=DEFAULT_ORDERS_PATH,
        help=f"orders CSV path (default: {DEFAULT_ORDERS_PATH.as_posix()})",
    )
    args = parser.parse_args()
    inspect_orders(args.path)


if __name__ == "__main__":
    main()

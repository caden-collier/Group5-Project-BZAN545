"""Snapshot the legacy and migrated product tables as raw CSV files.

The source database credentials are read from a gitignored JSON file with
``username`` and ``password`` keys.  Raw snapshots are never overwritten.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date
from pathlib import Path

import pymysql


DEFAULT_HOST = "mariadb-compx0.oit.utk.edu"
DEFAULT_DATABASE = "aspannba_bzan545"
DEFAULT_CREDENTIALS = Path("credentials.json")
DEFAULT_RAW_ROOT = Path("data/bronze/products")
TABLES = ("products", "new_products")


def read_credentials(path: Path) -> tuple[str, str]:
    """Read the expected username and password without printing either."""
    try:
        with path.open(encoding="utf-8") as credentials_file:
            credentials = json.load(credentials_file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Credentials file not found: {path}. Create this gitignored file "
            'with {"username": "...", "password": "..."} or pass '
            "--credentials PATH."
        ) from exc
    try:
        return credentials["username"], credentials["password"]
    except KeyError as exc:
        raise ValueError(
            f"{path} must contain username and password keys"
        ) from exc


def write_snapshot(
    output_path: Path,
    columns: list[str],
    rows: tuple[tuple[object, ...], ...],
) -> str:
    """Write a new CSV snapshot and return its SHA-256 digest."""
    if output_path.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing raw snapshot: {output_path}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(columns)
        writer.writerows(rows)

    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    output_path.with_suffix(".csv.sha256").write_text(
        f"{digest}  {output_path.name}\n",
        encoding="utf-8",
    )
    return digest


def export_tables(
    *,
    credentials_path: Path,
    raw_root: Path,
    snapshot_date: str,
    host: str,
    database: str,
) -> None:
    """Read both source tables and store date-stamped raw snapshots."""
    username, password = read_credentials(credentials_path)
    connection = pymysql.connect(
        host=host,
        user=username,
        password=password,
        database=database,
        port=3306,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.Cursor,
        read_timeout=30,
        write_timeout=30,
    )

    try:
        for table_name in TABLES:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT * FROM `{table_name}`")
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]

            output_path = raw_root / snapshot_date / f"{table_name}.csv"
            digest = write_snapshot(output_path, columns, rows)
            print(
                f"{table_name}: {len(rows)} rows, {len(columns)} columns -> "
                f"{output_path.as_posix()} (sha256 {digest[:12]}...)"
            )
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--credentials",
        type=Path,
        default=DEFAULT_CREDENTIALS,
        help="gitignored JSON credentials file",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument(
        "--snapshot-date",
        default=date.today().isoformat(),
        help="snapshot directory name (default: today)",
    )
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    args = parser.parse_args()

    export_tables(
        credentials_path=args.credentials,
        raw_root=args.raw_root,
        snapshot_date=args.snapshot_date,
        host=args.host,
        database=args.database,
    )


if __name__ == "__main__":
    main()

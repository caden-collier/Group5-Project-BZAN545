"""Command-line interface for the Group 5 pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import BRONZE_ORDERS_DIR
from .ingestion import replay_raw_ingestions, run_ingestion
from .orders import inspect_orders
from .pipeline import run_daily_pipeline
from .weather import sync_weather


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bzan545")
    commands = parser.add_subparsers(dest="command", required=True)
    daily = commands.add_parser("daily", help="ingest orders, log, and sync weather")
    daily.add_argument(
        "--skip-weather", action="store_true", help="run orders ingestion only"
    )
    commands.add_parser("ingest", help="ingest orders and update the audit log")
    inspect = commands.add_parser("inspect", help="validate and summarize a raw file")
    inspect.add_argument("path", type=Path, help="path to an orders CSV")
    commands.add_parser("replay", help="backfill log events from preserved raw orders")
    weather = commands.add_parser("weather", help="sync weather for an ISO date")
    weather.add_argument("date", help="order date in YYYY-MM-DD format")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "daily":
        return run_daily_pipeline(skip_weather=args.skip_weather)
    if args.command == "ingest":
        return 0 if run_ingestion().succeeded else 1
    if args.command == "inspect":
        inspect_orders(args.path)
        return 0
    if args.command == "replay":
        _, failures = replay_raw_ingestions(bronze_root=BRONZE_ORDERS_DIR)
        return 1 if failures else 0
    if args.command == "weather":
        sync_weather(args.date)
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")

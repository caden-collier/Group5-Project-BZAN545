"""Orchestrate the complete daily orders and weather workflow."""

from __future__ import annotations

from .ingestion import run_ingestion
from .weather import sync_weather


def run_daily_pipeline(*, skip_weather: bool = False) -> int:
    result = run_ingestion()
    if not result.succeeded or result.facts is None:
        return 1
    if not skip_weather:
        sync_weather(result.facts.order_date)
    return 0

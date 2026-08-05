"""Orchestrate the complete daily orders and weather workflow."""

from __future__ import annotations

from .ingestion import run_ingestion
from .weather import sync_weather
from .gold_sales import build_gold_sales
from .silver_orders import build_silver_orders

def rebuild_analytics() -> int:
    """Rebuild silver and gold from preserved bronze data."""
    build_silver_orders()
    build_gold_sales()
    return 0


def run_daily_pipeline(*, skip_weather: bool = False) -> int:
    result = run_ingestion()

    if not result.succeeded or result.facts is None:
        return 1

    if not skip_weather:
        sync_weather(result.facts.order_date)
        rebuild_analytics()

    return 0
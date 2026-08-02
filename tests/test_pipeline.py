from __future__ import annotations

import unittest
from unittest.mock import patch

from bzan545.ingestion import IngestionResult
from bzan545.orders import ValidatedOrders
from bzan545.pipeline import run_daily_pipeline


FACTS = ValidatedOrders("2026-07-31", 1, "abc", 10, "new_product_id")


class PipelineTests(unittest.TestCase):
    @patch("bzan545.pipeline.sync_weather")
    @patch("bzan545.pipeline.run_ingestion")
    def test_weather_uses_the_ingested_order_date(self, ingest, weather) -> None:
        ingest.return_value = IngestionResult(True, facts=FACTS)
        self.assertEqual(run_daily_pipeline(), 0)
        weather.assert_called_once_with("2026-07-31")

    @patch("bzan545.pipeline.sync_weather")
    @patch("bzan545.pipeline.run_ingestion")
    def test_failed_ingestion_stops_before_weather(self, ingest, weather) -> None:
        ingest.return_value = IngestionResult(False, error_message="failed")
        self.assertEqual(run_daily_pipeline(), 1)
        weather.assert_not_called()


if __name__ == "__main__":
    unittest.main()

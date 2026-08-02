from __future__ import annotations

import unittest
import urllib.parse

from bzan545.weather import Store, WeatherError, build_weather_url, parse_weather_response


class WeatherTests(unittest.TestCase):
    def test_url_uses_coordinates_date_variables_and_auto_timezone(self) -> None:
        url = build_weather_url(Store("S001", 35.96, -83.92), "2026-07-31")
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertEqual(query["start_date"], ["2026-07-31"])
        self.assertEqual(query["end_date"], ["2026-07-31"])
        self.assertEqual(query["timezone"], ["auto"])
        self.assertIn("precipitation_sum", query["daily"][0])

    def test_response_is_validated_and_converted(self) -> None:
        payload = {"daily": {
            "time": ["2026-07-31"], "temperature_2m_max": [31.2],
            "temperature_2m_min": [20.1], "precipitation_sum": [4.5],
        }}
        row = parse_weather_response(payload, "S001", "2026-07-31")
        self.assertEqual(row.temperature_2m_max_c, 31.2)
        self.assertEqual(row.precipitation_sum_mm, 4.5)
        with self.assertRaises(WeatherError):
            parse_weather_response({}, "S001", "2026-07-31")


if __name__ == "__main__":
    unittest.main()

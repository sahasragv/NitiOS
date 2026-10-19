"""Tests for the built-in basics tools, with HTTP services mocked."""

from __future__ import annotations

import unittest

import httpx

from app.mcp_servers.basics import tools


class CalculatorTests(unittest.TestCase):
    """Verify safe arithmetic evaluation."""

    def test_evaluates_arithmetic_and_functions(self) -> None:
        self.assertEqual(tools.calculate("(12.5 * 4) / 2"), "(12.5 * 4) / 2 = 25")
        self.assertEqual(tools.calculate("2 ^ 10"), "2 ^ 10 = 1024")
        self.assertEqual(tools.calculate("sqrt(16) + abs(-1)"), "sqrt(16) + abs(-1) = 5")

    def test_rejects_unsafe_or_expensive_expressions(self) -> None:
        for expression in ("__import__('os')", "open('x')", "9 ** 9 ** 9", "1 / 0", "x + 1"):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                tools.calculate(expression)


class TimeTests(unittest.TestCase):
    """Verify time-zone handling."""

    def test_converts_between_zones_on_a_fixed_date(self) -> None:
        result = tools.convert_time("09:30", "America/New_York", "Asia/Kolkata", "2026-01-15")
        self.assertEqual(result, "2026-01-15 09:30 America/New_York = 2026-01-15 20:00 Asia/Kolkata (UTC+0530)")

    def test_unknown_zone_has_helpful_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "IANA"):
            tools.current_time("Mars/Base")


class HttpToolTests(unittest.IsolatedAsyncioTestCase):
    """Verify weather and translation response parsing."""

    async def test_weather_formats_current_conditions(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "geocoding" in request.url.host:
                return httpx.Response(200, json={"results": [{"name": "Hyderabad", "country": "India", "latitude": 17.4, "longitude": 78.5}]})
            return httpx.Response(200, json={
                "current": {"time": "2026-01-15T10:00", "temperature_2m": 28, "apparent_temperature": 30, "relative_humidity_2m": 40, "weather_code": 2, "wind_speed_10m": 9},
                "daily": {"temperature_2m_max": [31], "temperature_2m_min": [19], "precipitation_probability_max": [5]},
            })

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await tools.get_weather("Hyderabad", client)
        self.assertIn("Hyderabad, India", result)
        self.assertIn("partly cloudy, 28°C", result)

    async def test_weather_unknown_place(self) -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={}))) as client:
            with self.assertRaisesRegex(ValueError, "Could not find"):
                await tools.get_weather("Nowhere", client)

    async def test_translation_sends_language_pair(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.params["langpair"], "en|fr")
            return httpx.Response(200, json={"responseStatus": 200, "responseData": {"translatedText": "Bonjour"}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            self.assertEqual(await tools.translate("Hello", "FR", client=client), "Bonjour")

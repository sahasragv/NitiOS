"""Everyday utilities that need no API keys: math, time zones, weather, translation.

This module is imported by a stdio MCP server subprocess, so it must never
write to stdout and must not import application logging.
"""

from __future__ import annotations

import ast
import math
import operator
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx


_HTTP_TIMEOUT_SECONDS = 15.0
_MAX_EXPRESSION_LENGTH = 200
_MAX_EXPONENT = 1000

_BINARY_OPERATORS: dict[type[ast.operator], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS: dict[type[ast.unaryop], Any] = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCTIONS: dict[str, Any] = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "radians": math.radians,
    "degrees": math.degrees,
}
_CONSTANTS: dict[str, float] = {"pi": math.pi, "e": math.e}

# WMO weather interpretation codes used by Open-Meteo.
_WEATHER_CODES: dict[int, str] = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


def calculate(expression: str) -> str:
    """Safely evaluate an arithmetic expression without using ``eval``."""
    if len(expression) > _MAX_EXPRESSION_LENGTH:
        raise ValueError(f"Expression is longer than {_MAX_EXPRESSION_LENGTH} characters.")
    try:
        tree = ast.parse(expression.replace("^", "**"), mode="eval")
    except SyntaxError as error:
        raise ValueError(f"Invalid expression: {expression}") from error
    result = _evaluate(tree.body)
    if isinstance(result, float) and result.is_integer() and abs(result) < 1e15:
        result = int(result)
    return f"{expression} = {result}"


def _evaluate(node: ast.expr) -> int | float:
    """Evaluate a whitelisted subset of Python expression nodes."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _UNARY_OPERATORS[type(node.op)](_evaluate(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left, right = _evaluate(node.left), _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > _MAX_EXPONENT:
            raise ValueError(f"Exponents larger than {_MAX_EXPONENT} are not allowed.")
        try:
            return _BINARY_OPERATORS[type(node.op)](left, right)
        except ZeroDivisionError as error:
            raise ValueError("Division by zero.") from error
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _FUNCTIONS
        and not node.keywords
    ):
        return _FUNCTIONS[node.func.id](*(_evaluate(argument) for argument in node.args))
    raise ValueError("Only numbers, + - * / // % ** and basic math functions are allowed.")


def _zone(name: str) -> ZoneInfo:
    """Resolve an IANA time zone name with a helpful error."""
    try:
        return ZoneInfo(name.strip())
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError(
            f"Unknown time zone '{name}'. Use an IANA name such as 'Asia/Kolkata', 'Europe/London' or 'America/New_York'."
        ) from error


def current_time(timezone: str = "UTC") -> str:
    """Return the current date and time in ``timezone``."""
    now = datetime.now(_zone(timezone))
    return f"{now:%A, %d %B %Y, %H:%M:%S} ({timezone}, UTC{now:%z})"


def convert_time(time_text: str, from_timezone: str, to_timezone: str, date_text: str | None = None) -> str:
    """Convert a wall-clock time (``HH:MM``) on ``date_text`` (``YYYY-MM-DD``, default today) between zones."""
    source_zone, target_zone = _zone(from_timezone), _zone(to_timezone)
    try:
        wall_time = time.fromisoformat(time_text.strip())
        day = date.fromisoformat(date_text) if date_text else datetime.now(source_zone).date()
    except ValueError as error:
        raise ValueError("Use HH:MM for the time and YYYY-MM-DD for the date.") from error
    source = datetime.combine(day, wall_time, tzinfo=source_zone)
    target = source.astimezone(target_zone)
    return (
        f"{source:%Y-%m-%d %H:%M} {from_timezone} = {target:%Y-%m-%d %H:%M} {to_timezone} "
        f"(UTC{target:%z})"
    )


async def get_weather(location: str, client: httpx.AsyncClient | None = None) -> str:
    """Return current conditions and today's range for ``location`` using Open-Meteo."""
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS)
    try:
        geocoding = await http.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": location, "count": 1, "format": "json"},
        )
        geocoding.raise_for_status()
        places = geocoding.json().get("results") or []
        if not places:
            raise ValueError(f"Could not find a place named '{location}'.")
        place = places[0]

        forecast = await http.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "forecast_days": 1,
                "timezone": "auto",
            },
        )
        forecast.raise_for_status()
        data = forecast.json()
    except httpx.HTTPError as error:
        raise ValueError("The weather service is unavailable right now.") from error
    finally:
        if owns_client:
            await http.aclose()

    current, daily = data["current"], data["daily"]
    place_name = ", ".join(part for part in (place.get("name"), place.get("admin1"), place.get("country")) if part)
    conditions = _WEATHER_CODES.get(current.get("weather_code"), "unknown conditions")
    return (
        f"Weather in {place_name} (local time {current['time']}): {conditions}, "
        f"{current['temperature_2m']}°C (feels like {current['apparent_temperature']}°C), "
        f"humidity {current['relative_humidity_2m']}%, wind {current['wind_speed_10m']} km/h. "
        f"Today: high {daily['temperature_2m_max'][0]}°C, low {daily['temperature_2m_min'][0]}°C, "
        f"{daily['precipitation_probability_max'][0]}% chance of precipitation."
    )


async def translate(
    text: str,
    target_language: str,
    source_language: str = "en",
    client: httpx.AsyncClient | None = None,
) -> str:
    """Translate ``text`` between ISO 639-1 language codes using the free MyMemory API."""
    if len(text) > 500:
        raise ValueError("Text must be 500 characters or fewer.")
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS)
    try:
        response = await http.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text, "langpair": f"{source_language.strip().lower()}|{target_language.strip().lower()}"},
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as error:
        raise ValueError("The translation service is unavailable right now.") from error
    finally:
        if owns_client:
            await http.aclose()

    if data.get("responseStatus") != 200:
        raise ValueError(f"Translation failed: {data.get('responseDetails') or 'unknown error'}")
    return data["responseData"]["translatedText"]

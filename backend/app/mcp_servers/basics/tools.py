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


_TEMPERATURE_UNITS: dict[str, str] = {
    "c": "C", "celsius": "C", "°c": "C",
    "f": "F", "fahrenheit": "F", "°f": "F",
    "k": "K", "kelvin": "K",
}

# Each unit maps to (dimension, factor to the dimension's base unit).
_LINEAR_UNITS: dict[str, tuple[str, float]] = {
    # length, base metre
    "mm": ("length", 0.001), "millimeter": ("length", 0.001), "millimetre": ("length", 0.001),
    "cm": ("length", 0.01), "centimeter": ("length", 0.01), "centimetre": ("length", 0.01),
    "m": ("length", 1.0), "meter": ("length", 1.0), "metre": ("length", 1.0),
    "km": ("length", 1000.0), "kilometer": ("length", 1000.0), "kilometre": ("length", 1000.0),
    "in": ("length", 0.0254), "inch": ("length", 0.0254), "inches": ("length", 0.0254),
    "ft": ("length", 0.3048), "foot": ("length", 0.3048), "feet": ("length", 0.3048),
    "yd": ("length", 0.9144), "yard": ("length", 0.9144),
    "mi": ("length", 1609.344), "mile": ("length", 1609.344),
    # mass, base kilogram
    "mg": ("mass", 1e-6), "g": ("mass", 0.001), "gram": ("mass", 0.001),
    "kg": ("mass", 1.0), "kilogram": ("mass", 1.0),
    "t": ("mass", 1000.0), "tonne": ("mass", 1000.0),
    "oz": ("mass", 0.028349523125), "ounce": ("mass", 0.028349523125),
    "lb": ("mass", 0.45359237), "lbs": ("mass", 0.45359237), "pound": ("mass", 0.45359237),
    # volume, base litre
    "ml": ("volume", 0.001), "milliliter": ("volume", 0.001), "millilitre": ("volume", 0.001),
    "l": ("volume", 1.0), "liter": ("volume", 1.0), "litre": ("volume", 1.0),
    "cup": ("volume", 0.2365882365), "floz": ("volume", 0.0295735295625), "fl oz": ("volume", 0.0295735295625),
    "gal": ("volume", 3.785411784), "gallon": ("volume", 3.785411784),
    # speed, base metre per second
    "m/s": ("speed", 1.0), "km/h": ("speed", 1 / 3.6), "kmh": ("speed", 1 / 3.6), "kph": ("speed", 1 / 3.6),
    "mph": ("speed", 0.44704), "knot": ("speed", 0.514444), "knots": ("speed", 0.514444),
    # area, base square metre
    "m2": ("area", 1.0), "sq m": ("area", 1.0), "km2": ("area", 1e6), "sq km": ("area", 1e6),
    "ft2": ("area", 0.09290304), "sq ft": ("area", 0.09290304), "acre": ("area", 4046.8564224), "hectare": ("area", 10000.0), "ha": ("area", 10000.0),
    # digital storage, base byte (binary multiples)
    "b": ("data", 1.0), "byte": ("data", 1.0), "kb": ("data", 1024.0), "mb": ("data", 1024.0**2),
    "gb": ("data", 1024.0**3), "tb": ("data", 1024.0**4),
}


def _normalize_unit(unit: str) -> str:
    """Lower-case a unit and drop a trailing plural 's' when that yields a known unit."""
    normalized = unit.strip().lower()
    if normalized not in _LINEAR_UNITS and normalized.endswith("s") and normalized[:-1] in _LINEAR_UNITS:
        return normalized[:-1]
    return normalized


def _format_number(value: float) -> str:
    """Round to a readable precision without scientific notation for everyday values."""
    return f"{value:,.6f}".rstrip("0").rstrip(".") if abs(value) < 1e12 else f"{value:.6g}"


def convert_units(value: float, from_unit: str, to_unit: str) -> str:
    """Convert ``value`` between units of temperature, length, mass, volume, speed, area or data size."""
    source, target = _normalize_unit(from_unit), _normalize_unit(to_unit)
    if source in _TEMPERATURE_UNITS and target in _TEMPERATURE_UNITS:
        source_scale, target_scale = _TEMPERATURE_UNITS[source], _TEMPERATURE_UNITS[target]
        celsius = {"C": value, "F": (value - 32) * 5 / 9, "K": value - 273.15}[source_scale]
        result = {"C": celsius, "F": celsius * 9 / 5 + 32, "K": celsius + 273.15}[target_scale]
        return f"{_format_number(value)} °{source_scale} = {_format_number(result)} °{target_scale}".replace("°K", "K")

    if source not in _LINEAR_UNITS or target not in _LINEAR_UNITS:
        unknown = from_unit if source not in _LINEAR_UNITS and source not in _TEMPERATURE_UNITS else to_unit
        raise ValueError(f"Unknown unit '{unknown}'. Try units like km, mi, kg, lb, l, gal, km/h, mph, sq ft, GB or C/F/K.")
    (source_dimension, source_factor), (target_dimension, target_factor) = _LINEAR_UNITS[source], _LINEAR_UNITS[target]
    if source_dimension != target_dimension:
        raise ValueError(f"Cannot convert {source_dimension} ({from_unit}) to {target_dimension} ({to_unit}).")
    result = value * source_factor / target_factor
    return f"{_format_number(value)} {from_unit.strip()} = {_format_number(result)} {to_unit.strip()}"


async def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Convert money using the latest European Central Bank reference rates from Frankfurter."""
    source, target = from_currency.strip().upper(), to_currency.strip().upper()
    if source == target:
        return f"{_format_number(amount)} {source} = {_format_number(amount)} {target}"
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS)
    try:
        response = await http.get(
            "https://api.frankfurter.dev/v1/latest",
            params={"base": source, "symbols": target, "amount": amount},
        )
        if response.status_code == 404:
            raise ValueError("Unsupported currency. Use ISO codes such as USD, EUR, INR, GBP or JPY.")
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as error:
        raise ValueError("The currency service is unavailable right now.") from error
    finally:
        if owns_client:
            await http.aclose()

    rate_total = data.get("rates", {}).get(target)
    if rate_total is None:
        raise ValueError(f"No exchange rate available for {source} to {target}.")
    return f"{_format_number(amount)} {source} = {rate_total:,.2f} {target} (ECB reference rate, {data.get('date', 'latest')})"


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

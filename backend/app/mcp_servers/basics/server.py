"""stdio MCP server exposing Setu's built-in everyday tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.mcp_servers.basics import tools


server = FastMCP("setu-basics", log_level="WARNING")


@server.tool()
def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression exactly, e.g. '(12.5 * 4) / 3' or 'sqrt(2) ^ 10'.

    Supports + - * / // % ** (or ^), parentheses, pi, e and sqrt, abs, round,
    floor, ceil, log, log10, exp, sin, cos, tan, radians, degrees.
    """
    return tools.calculate(expression)


@server.tool()
def current_time(timezone: str = "UTC") -> str:
    """Get the current date and time in an IANA time zone such as 'Asia/Kolkata' or 'America/New_York'."""
    return tools.current_time(timezone)


@server.tool()
def convert_time(time: str, from_timezone: str, to_timezone: str, date: str | None = None) -> str:
    """Convert a time between IANA time zones.

    Args:
        time: Wall-clock time as HH:MM (24-hour).
        from_timezone: Source zone, e.g. 'Europe/London'.
        to_timezone: Target zone, e.g. 'Asia/Tokyo'.
        date: Optional date as YYYY-MM-DD; defaults to today in the source zone.
    """
    return tools.convert_time(time, from_timezone, to_timezone, date)


@server.tool()
def convert_units(value: float, from_unit: str, to_unit: str) -> str:
    """Convert a value between units, exactly. Use this instead of writing a formula.

    Supports temperature (C, F, K), length (mm, cm, m, km, in, ft, yd, mi), mass (mg, g, kg, t, oz, lb),
    volume (ml, l, cup, fl oz, gal), speed (m/s, km/h, mph, knots), area (m2, km2, sq ft, acre, hectare)
    and data size (B, KB, MB, GB, TB).
    """
    return tools.convert_units(value, from_unit, to_unit)


@server.tool()
async def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert money between currencies at today's reference rate, using ISO codes like USD, EUR, INR, GBP, JPY."""
    return await tools.convert_currency(amount, from_currency, to_currency)


@server.tool()
async def get_weather(location: str) -> str:
    """Get the current weather and today's forecast for a city or place name, e.g. 'Hyderabad'."""
    return await tools.get_weather(location)


@server.tool()
async def translate(text: str, target_language: str, source_language: str = "en") -> str:
    """Translate a specific piece of text the user supplied (max 500 characters) between ISO 639-1 language codes,
    e.g. source 'en', target 'hi', 'te', 'ta', 'fr', 'ja'.

    Only for explicit "translate this text" requests. To answer a question in another language,
    write the answer directly in that language instead of calling this tool.
    """
    return await tools.translate(text, target_language, source_language)

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
async def get_weather(location: str) -> str:
    """Get the current weather and today's forecast for a city or place name, e.g. 'Hyderabad'."""
    return await tools.get_weather(location)


@server.tool()
async def translate(text: str, target_language: str, source_language: str = "en") -> str:
    """Translate text between languages using ISO 639-1 codes, e.g. source 'en', target 'hi', 'fr', 'ja'."""
    return await tools.translate(text, target_language, source_language)

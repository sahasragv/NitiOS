"""Setu application entry point."""

from app.startup.application import create_application


app = create_application()
"""ASGI application instance for deployment servers."""

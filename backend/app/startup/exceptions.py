"""Exception-handler registration for application startup."""

from fastapi import FastAPI

from app.exceptions.handlers import register_exception_handlers as register_handlers


def register_exception_handlers(app: FastAPI) -> None:
    """Register the platform's global exception handlers on ``app``."""
    register_handlers(app)

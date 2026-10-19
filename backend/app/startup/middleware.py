"""Middleware registration for application startup."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import settings


def register_middlewares(app: FastAPI) -> None:
    """Register middleware on ``app``."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

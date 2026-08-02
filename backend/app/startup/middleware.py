"""Middleware registration placeholder for application startup."""

from fastapi import FastAPI


def register_middlewares(app: FastAPI) -> None:
    """Register middleware on ``app`` when middleware is introduced."""
    del app

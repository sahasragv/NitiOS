"""FastAPI application factory for the Setu backend."""

from fastapi import FastAPI

from app.core.settings import settings
from app.startup.exceptions import register_exception_handlers
from app.startup.lifespan import get_lifespan
from app.startup.middleware import register_middlewares
from app.startup.routes import register_routes


def create_application() -> FastAPI:
    """Create and return the configured Setu FastAPI application.

    Routes, middleware, and exception handlers should be composed here as their
    respective startup modules are introduced.
    """
    application = FastAPI(title=settings.APP_NAME, lifespan=get_lifespan())
    register_exception_handlers(application)
    register_middlewares(application)
    register_routes(application)

    return application

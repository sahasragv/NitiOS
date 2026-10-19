"""Centralized logging configuration for the Setu backend."""

import logging
from logging.config import dictConfig
from threading import Lock
from typing import Any

from app.core.settings import settings


_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
_configuration_lock = Lock()
_is_configured = False


def configure_logging() -> None:
    """Configure application logging exactly once.

    The configuration emits records to standard output and preserves existing
    library loggers. Future JSON, tracing, and correlation-ID formatters can be
    introduced here without changing logging call sites.
    """
    global _is_configured

    with _configuration_lock:
        if _is_configured:
            return

        logging_configuration: dict[str, Any] = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": _LOG_FORMAT,
                    "datefmt": _DATE_FORMAT,
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": settings.LOG_LEVEL,
                    "formatter": "standard",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": settings.LOG_LEVEL,
                "handlers": ["console"],
            },
        }

        dictConfig(logging_configuration)
        _is_configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger identified by ``name``.

    Args:
        name: Usually the caller's module name, such as ``__name__``.

    Returns:
        A standard-library logger using the centralized application configuration.
    """
    configure_logging()
    return logging.getLogger(name)

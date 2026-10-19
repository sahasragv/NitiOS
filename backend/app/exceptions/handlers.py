"""FastAPI exception adapters for standard Setu error responses."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.common.responses import ErrorDetails, ErrorResponse
from app.core.logging import get_logger
from app.exceptions.base import BaseApplicationException


_logger = get_logger(__name__)


def _create_error_response(
    *,
    message: str,
    error_code: str,
    details: dict[str, Any] | None = None,
) -> ErrorResponse:
    """Build the standard error envelope used by all exception handlers."""
    return ErrorResponse(
        message=message,
        error=ErrorDetails(code=error_code, details=details),
    )


def _to_json_response(
    error_response: ErrorResponse,
    status_code: int,
) -> JSONResponse:
    """Serialize a standard error envelope as an HTTP JSON response."""
    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump(mode="json"),
    )


async def handle_application_exception(
    request: Request,
    exception: BaseApplicationException,
) -> JSONResponse:
    """Convert an expected application exception into a standard error response."""
    del request
    error_response = _create_error_response(
        message=exception.message,
        error_code=exception.error_code,
    )
    return _to_json_response(error_response, exception.status_code)


async def handle_http_exception(
    request: Request,
    exception: HTTPException,
) -> JSONResponse:
    """Convert an HTTP exception into a standard error response."""
    del request
    message = exception.detail if isinstance(exception.detail, str) else "HTTP request failed."
    error_response = _create_error_response(
        message=message,
        error_code="HTTP_ERROR",
        details={"detail": exception.detail},
    )
    return _to_json_response(error_response, exception.status_code)


async def handle_request_validation_error(
    request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    """Convert a request validation failure into a standard error response."""
    del request
    error_response = _create_error_response(
        message="Request validation failed.",
        error_code="REQUEST_VALIDATION_ERROR",
        details={"errors": exception.errors()},
    )
    return _to_json_response(error_response, status_code=422)


async def handle_unexpected_exception(
    request: Request,
    exception: Exception,
) -> JSONResponse:
    """Log and convert an unexpected exception into a safe error response."""
    _logger.exception(
        "Unhandled application exception.",
        extra={"request_path": request.url.path},
        exc_info=exception,
    )
    error_response = _create_error_response(
        message="An unexpected error occurred.",
        error_code="INTERNAL_SERVER_ERROR",
    )
    return _to_json_response(error_response, status_code=500)


def register_exception_handlers(app: FastAPI) -> None:
    """Register every Setu exception handler on a FastAPI application."""
    app.add_exception_handler(BaseApplicationException, handle_application_exception)
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_request_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_exception)

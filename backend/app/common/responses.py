"""Reusable API response models for the NitiOS platform."""

from datetime import datetime, timezone
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class ResponseMeta(BaseModel):
    """Metadata included with API responses."""

    request_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str | None = None


class ErrorDetails(BaseModel):
    """Structured details describing an API error."""

    code: str
    details: dict[str, Any] | None = None


class SuccessResponse(BaseModel, Generic[T]):
    """Standard response envelope for successful operations."""

    success: Literal[True] = True
    message: str
    data: T
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


class ErrorResponse(BaseModel):
    """Standard response envelope for failed operations."""

    success: Literal[False] = False
    message: str
    error: ErrorDetails
    meta: ResponseMeta = Field(default_factory=ResponseMeta)

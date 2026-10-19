"""Async HTTP transport for the Anthropic Messages API."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.modules.llm.domain.interfaces import LLMProviderInfrastructureError


ANTHROPIC_API_VERSION = "2023-06-01"


class AnthropicProviderError(LLMProviderInfrastructureError):
    """A safe, provider-level communication failure from the Anthropic adapter."""

    def __init__(self, message: str, *, status_code: int | None = None, reason: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason


def create_anthropic_http_client(*, base_url: str, api_key: str, timeout_seconds: float) -> httpx.AsyncClient:
    """Build the shared ``AsyncClient`` with authentication and version headers applied."""
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(timeout_seconds),
        headers={"x-api-key": api_key, "anthropic-version": ANTHROPIC_API_VERSION},
    )


class AnthropicClient:
    """HTTP-only client for ``POST /v1/messages`` using a lifespan-managed ``AsyncClient``."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client

    async def create_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a non-streaming Messages request and return the JSON response."""
        try:
            response = await self._client.post("/v1/messages", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            raise self._status_error(error) from error
        except (httpx.HTTPError, ValueError) as error:
            raise AnthropicProviderError("Unable to communicate with Anthropic.", reason=type(error).__name__) from error

    async def stream_message(self, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """Yield each decoded Server-Sent Event payload from a streaming Messages request."""
        try:
            async with self._client.stream("POST", "/v1/messages", json=payload) as response:
                if response.is_error:
                    await response.aread()
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    event = json.loads(line[5:].strip())
                    if event.get("type") == "error":
                        raise AnthropicProviderError(
                            "Anthropic reported a streaming error.",
                            reason=str(event.get("error", {}).get("type") or "stream_error"),
                        )
                    yield event
        except AnthropicProviderError:
            raise
        except httpx.HTTPStatusError as error:
            raise self._status_error(error) from error
        except (httpx.HTTPError, ValueError) as error:
            raise AnthropicProviderError("Unable to communicate with Anthropic.", reason=type(error).__name__) from error

    @staticmethod
    def _status_error(error: httpx.HTTPStatusError) -> AnthropicProviderError:
        """Map an HTTP failure, keeping Anthropic's error type (e.g. ``authentication_error``) as the reason."""
        try:
            reason = error.response.json().get("error", {}).get("type") or "http_status_error"
        except ValueError:
            reason = "http_status_error"
        return AnthropicProviderError("Anthropic rejected the request.", status_code=error.response.status_code, reason=reason)

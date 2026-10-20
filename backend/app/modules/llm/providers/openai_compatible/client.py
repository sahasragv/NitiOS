"""Async HTTP transport for OpenAI-compatible Chat Completions endpoints."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.modules.llm.domain.interfaces import LLMProviderInfrastructureError


class OpenAICompatibleProviderError(LLMProviderInfrastructureError):
    """A safe, provider-level communication failure from an OpenAI-compatible adapter."""

    def __init__(self, message: str, *, status_code: int | None = None, reason: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason


def create_openai_compatible_http_client(*, base_url: str, api_key: str, timeout_seconds: float) -> httpx.AsyncClient:
    """Build the shared ``AsyncClient`` with bearer authentication applied."""
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(timeout_seconds),
        headers={"Authorization": f"Bearer {api_key}"},
    )


class OpenAICompatibleClient:
    """HTTP-only client for ``POST /chat/completions`` using a lifespan-managed ``AsyncClient``."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client

    async def create_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a non-streaming completion request and return the JSON response."""
        try:
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            raise self._status_error(error) from error
        except (httpx.HTTPError, ValueError) as error:
            raise OpenAICompatibleProviderError("Unable to communicate with the model provider.", reason=type(error).__name__) from error

    async def stream_completion(self, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """Yield each decoded Server-Sent Event chunk until the ``[DONE]`` marker."""
        try:
            async with self._client.stream("POST", "/chat/completions", json=payload) as response:
                if response.is_error:
                    await response.aread()
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    yield json.loads(data)
        except httpx.HTTPStatusError as error:
            raise self._status_error(error) from error
        except (httpx.HTTPError, ValueError) as error:
            raise OpenAICompatibleProviderError("Unable to communicate with the model provider.", reason=type(error).__name__) from error

    @staticmethod
    def _status_error(error: httpx.HTTPStatusError) -> OpenAICompatibleProviderError:
        """Map an HTTP failure, keeping the provider's error status (e.g. ``RESOURCE_EXHAUSTED``) as the reason."""
        try:
            body = error.response.json()
            # Gemini sometimes wraps the error object in a one-element list.
            details = (body[0] if isinstance(body, list) and body else body).get("error", {})
            reason = details.get("status") or details.get("type") or details.get("code") or "http_status_error"
        except (ValueError, AttributeError):
            reason = "http_status_error"
        return OpenAICompatibleProviderError(
            "The model provider rejected the request.",
            status_code=error.response.status_code,
            reason=str(reason),
        )

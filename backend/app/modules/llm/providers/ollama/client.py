"""Async HTTP transport for Ollama's local API."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.modules.llm.domain.interfaces import LLMProviderInfrastructureError


class OllamaProviderError(LLMProviderInfrastructureError):
    """A safe, provider-level communication failure from the Ollama adapter."""

    def __init__(self, message: str, *, status_code: int | None = None, reason: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason


class OllamaClient:
    """HTTP-only client for Ollama using a lifespan-managed shared ``AsyncClient``."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
    ) -> None:
        self._client = http_client

    async def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a non-streaming chat request and return Ollama's JSON payload."""
        try:
            response = await self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            raise OllamaProviderError(
                "Ollama rejected the request.",
                status_code=error.response.status_code,
                reason="http_status_error",
            ) from error
        except (httpx.HTTPError, ValueError) as error:
            raise OllamaProviderError("Unable to communicate with Ollama.", reason=type(error).__name__) from error

    async def stream(self, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """Yield decoded JSON objects from Ollama's newline-delimited streaming response."""
        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        yield json.loads(line)
        except OllamaProviderError:
            raise
        except httpx.HTTPStatusError as error:
            raise OllamaProviderError(
                "Ollama rejected the request.",
                status_code=error.response.status_code,
                reason="http_status_error",
            ) from error
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise OllamaProviderError("Unable to communicate with Ollama.", reason=type(error).__name__) from error

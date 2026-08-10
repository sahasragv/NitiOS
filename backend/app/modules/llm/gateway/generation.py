"""Stateless gateway for provider-neutral LLM generation operations."""

from __future__ import annotations

from collections.abc import AsyncIterator
from time import perf_counter

from app.core.logging import get_logger
from app.modules.llm.domain.interfaces import GenerationProvider
from app.modules.llm.domain.models import LLMRequest, LLMResponse, LLMStreamChunk


class LLMGatewayRequestError(ValueError):
    """Raised when a request cannot be sent to a generation provider."""


class LLMGateway:
    """Delegate generation work to an injected provider without provider coupling."""

    def __init__(self, provider: GenerationProvider) -> None:
        self._provider = provider
        self._logger = get_logger(__name__)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Validate and delegate a complete generation request to the configured provider."""
        self._validate_request(request)
        started_at = perf_counter()
        try:
            response = await self._provider.generate(request)
            self._log_outcome(request, latency_ms=(perf_counter() - started_at) * 1000, success=True, model=response.model)
            return response
        except Exception:
            self._log_outcome(request, latency_ms=(perf_counter() - started_at) * 1000, success=False)
            raise

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        """Validate and relay streaming chunks as they are received from the provider."""
        self._validate_request(request)
        started_at = perf_counter()
        try:
            async for chunk in self._provider.stream(request):
                yield chunk
            self._log_outcome(request, latency_ms=(perf_counter() - started_at) * 1000, success=True)
        except Exception:
            self._log_outcome(request, latency_ms=(perf_counter() - started_at) * 1000, success=False)
            raise

    @staticmethod
    def _validate_request(request: LLMRequest) -> None:
        """Enforce the gateway invariant that a generation request has input messages."""
        if not request.messages:
            raise LLMGatewayRequestError("Generation requests must contain at least one message.")

    def _log_outcome(self, request: LLMRequest, *, latency_ms: float, success: bool, model: str | None = None) -> None:
        """Emit safe gateway telemetry without request or response content."""
        log_method = self._logger.info if success else self._logger.error
        log_method(
            "LLM gateway generation completed" if success else "LLM gateway generation failed",
            extra={
                "request_id": request.metadata.request_id,
                "capability": request.capability.value,
                "provider": self._provider.name,
                "model": model,
                "latency_ms": round(latency_ms, 2),
                "success": success,
            },
        )

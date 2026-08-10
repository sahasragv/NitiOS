"""Generation adapter translating NitiOS contracts to and from Ollama chat requests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from time import perf_counter
from typing import Any

from app.core.logging import get_logger
from app.modules.llm.domain.interfaces import GenerationProvider
from app.modules.llm.domain.models import (
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    LLMUsage,
    ResponseMetadata,
)
from app.modules.llm.providers.ollama.client import OllamaClient, OllamaProviderError


class OllamaGenerationProvider(GenerationProvider):
    """Provider-neutral generation implementation backed by Ollama's chat API."""

    def __init__(self, client: OllamaClient, default_model: str) -> None:
        self._client = client
        self._default_model = default_model
        self._logger = get_logger(__name__)

    @property
    def name(self) -> str:
        """Return this adapter's stable application-level provider name."""
        return "ollama"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a complete response from Ollama for a NitiOS request."""
        started_at = perf_counter()
        request_id = request.metadata.request_id
        try:
            payload = self._to_ollama_payload(request, stream=False)
            result = await self._client.generate(payload)
            latency_ms = (perf_counter() - started_at) * 1000
            response = self._to_response(result, request_id=request_id, latency_ms=latency_ms)
            self._log_outcome(model=response.model, request_id=request_id, latency_ms=latency_ms, success=True)
            return response
        except OllamaProviderError as error:
            latency_ms = (perf_counter() - started_at) * 1000
            self._log_outcome(
                model=self._default_model,
                request_id=request_id,
                latency_ms=latency_ms,
                success=False,
                error=error,
            )
            raise

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        """Yield provider-neutral content chunks from Ollama's streaming API."""
        started_at = perf_counter()
        request_id = request.metadata.request_id
        try:
            payload = self._to_ollama_payload(request, stream=True)
            async for item in self._client.stream(payload):
                message = item.get("message", {})
                yield LLMStreamChunk(
                    content_delta=message.get("content") or None,
                    finish_reason=item.get("done_reason") if item.get("done") else None,
                    metadata=ResponseMetadata(request_id=request_id),
                )
            self._log_outcome(
                model=self._default_model,
                request_id=request_id,
                latency_ms=(perf_counter() - started_at) * 1000,
                success=True,
            )
        except OllamaProviderError as error:
            self._log_outcome(
                model=self._default_model,
                request_id=request_id,
                latency_ms=(perf_counter() - started_at) * 1000,
                success=False,
                error=error,
            )
            raise

    def _to_ollama_payload(self, request: LLMRequest, *, stream: bool) -> dict[str, Any]:
        """Translate prepared messages; Context Engineering prepares context before this boundary."""
        if request.response_format.type == "structured":
            raise OllamaProviderError(
                "Structured output is not supported by the Ollama generation provider.",
                reason="unsupported_response_format",
            )

        options: dict[str, Any] = {}
        if request.generation.temperature is not None:
            options["temperature"] = request.generation.temperature
        if request.generation.max_tokens is not None:
            options["num_predict"] = request.generation.max_tokens
        if request.generation.top_p is not None:
            options["top_p"] = request.generation.top_p
        if request.generation.stop_sequences:
            options["stop"] = request.generation.stop_sequences

        payload: dict[str, Any] = {
            "model": self._default_model,
            "messages": [{"role": message.role, "content": message.content} for message in request.messages],
            "stream": stream,
        }
        if options:
            payload["options"] = options
        if request.response_format.type == "json":
            payload["format"] = "json"
        return payload

    def _to_response(self, result: dict[str, Any], *, request_id: str | None, latency_ms: float) -> LLMResponse:
        """Normalize an Ollama completion while retaining only generic response data."""
        message = result.get("message", {})
        input_tokens = self._as_non_negative_int(result.get("prompt_eval_count"))
        output_tokens = self._as_non_negative_int(result.get("eval_count"))
        return LLMResponse(
            content=message.get("content") or None,
            provider=self.name,
            model=str(result.get("model") or self._default_model),
            usage=LLMUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=input_tokens + output_tokens),
            finish_reason=result.get("done_reason") or None,
            latency_ms=latency_ms,
            metadata=ResponseMetadata(request_id=request_id),
        )

    @staticmethod
    def _as_non_negative_int(value: object) -> int:
        """Normalize optional Ollama usage values without leaking provider response details."""
        return value if isinstance(value, int) and value >= 0 else 0

    def _log_outcome(
        self,
        *,
        model: str,
        request_id: str | None,
        latency_ms: float,
        success: bool,
        error: OllamaProviderError | None = None,
    ) -> None:
        """Log safe boundary telemetry without serializing requests or their contents."""
        log_method = self._logger.info if success else self._logger.error
        message = "Ollama generation completed" if success else (
            "Ollama generation failed | provider=%s model=%s request_id=%s "
            "error_reason=%s error_status=%s error_type=%s"
        )
        arguments: tuple[object, ...] = () if success else (
            self.name,
            model,
            request_id,
            error.reason if error else None,
            error.status_code if error else None,
            type(error).__name__ if error else None,
        )
        log_method(
            message,
            *arguments,
            extra={
                "provider": self.name,
                "model": model,
                "request_id": request_id,
                "latency_ms": round(latency_ms, 2),
                "success": success,
                "error_reason": error.reason if error else None,
                "error_status": error.status_code if error else None,
                "error_type": type(error).__name__ if error else None,
            },
        )

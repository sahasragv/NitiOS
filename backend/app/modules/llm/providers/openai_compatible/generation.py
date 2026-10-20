"""Generation adapter translating Setu contracts to and from OpenAI-compatible Chat Completions."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from time import perf_counter
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger
from app.modules.llm.domain.interfaces import GenerationProvider
from app.modules.llm.domain.models import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    LLMUsage,
    ResponseMetadata,
    ToolCall,
)
from app.modules.llm.providers.openai_compatible.client import OpenAICompatibleClient, OpenAICompatibleProviderError


class OpenAICompatibleGenerationProvider(GenerationProvider):
    """Provider-neutral generation over any Chat Completions API; ``provider_name`` labels it (e.g. ``gemini``)."""

    def __init__(
        self,
        client: OpenAICompatibleClient,
        default_model: str,
        *,
        provider_name: str,
        reasoning_effort: str | None = None,
    ) -> None:
        self._client = client
        self._default_model = default_model
        self._provider_name = provider_name
        self._reasoning_effort = reasoning_effort
        self._logger = get_logger(__name__)

    @property
    def name(self) -> str:
        """Return this adapter's stable application-level provider name."""
        return self._provider_name

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a complete response for a Setu request."""
        started_at = perf_counter()
        request_id = request.metadata.request_id
        try:
            result = await self._client.create_completion(self._to_payload(request, stream=False))
            latency_ms = (perf_counter() - started_at) * 1000
            response = self._to_response(result, request_id=request_id, latency_ms=latency_ms)
            self._log_outcome(request_id=request_id, latency_ms=latency_ms, success=True)
            return response
        except OpenAICompatibleProviderError as error:
            self._log_outcome(request_id=request_id, latency_ms=(perf_counter() - started_at) * 1000, success=False, error=error)
            raise

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        """Yield text deltas as they arrive and the tool calls once the response finishes."""
        started_at = perf_counter()
        request_id = request.metadata.request_id
        metadata = ResponseMetadata(request_id=request_id)
        # Tool calls may stream their name and JSON arguments in fragments, keyed by index.
        pending_tools: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        usage: LLMUsage | None = None
        try:
            async for chunk in self._client.stream_completion(self._to_payload(request, stream=True)):
                if chunk.get("usage"):
                    usage = self._to_usage(chunk["usage"])
                for choice in chunk.get("choices") or []:
                    delta = choice.get("delta") or {}
                    if delta.get("content"):
                        yield LLMStreamChunk(content_delta=delta["content"], metadata=metadata)
                    for fragment in delta.get("tool_calls") or []:
                        tool = pending_tools.setdefault(fragment.get("index", len(pending_tools)), {"id": None, "name": "", "json": [], "extra": {}})
                        function = fragment.get("function") or {}
                        tool["id"] = fragment.get("id") or tool["id"]
                        tool["name"] += function.get("name") or ""
                        tool["json"].append(function.get("arguments") or "")
                        if fragment.get("extra_content"):
                            tool["extra"]["extra_content"] = fragment["extra_content"]
                    finish_reason = choice.get("finish_reason") or finish_reason

            tool_calls = [
                ToolCall(
                    id=tool["id"] or f"call_{uuid4().hex[:12]}",
                    name=tool["name"],
                    arguments=self._parse_arguments("".join(tool["json"])),
                    provider_data=tool["extra"],
                )
                for _, tool in sorted(pending_tools.items())
                if tool["name"]
            ]
            yield LLMStreamChunk(tool_calls=tool_calls, finish_reason=finish_reason, usage=usage, metadata=metadata)
            self._log_outcome(request_id=request_id, latency_ms=(perf_counter() - started_at) * 1000, success=True)
        except OpenAICompatibleProviderError as error:
            self._log_outcome(request_id=request_id, latency_ms=(perf_counter() - started_at) * 1000, success=False, error=error)
            raise

    def _to_payload(self, request: LLMRequest, *, stream: bool) -> dict[str, Any]:
        """Translate prepared messages and tools into a Chat Completions request body."""
        if request.response_format.type == "structured":
            raise OpenAICompatibleProviderError(
                "Structured output is not supported by the OpenAI-compatible generation provider.",
                reason="unsupported_response_format",
            )

        payload: dict[str, Any] = {
            "model": self._default_model,
            "messages": [self._to_openai_message(message) for message in request.messages],
            "stream": stream,
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.input_schema or {"type": "object", "properties": {}},
                    },
                }
                for tool in request.tools
            ]
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort
        if request.generation.temperature is not None:
            payload["temperature"] = request.generation.temperature
        if request.generation.max_tokens is not None:
            payload["max_tokens"] = request.generation.max_tokens
        if request.generation.top_p is not None:
            payload["top_p"] = request.generation.top_p
        if request.generation.stop_sequences:
            payload["stop"] = request.generation.stop_sequences
        if request.response_format.type == "json":
            payload["response_format"] = {"type": "json_object"}
        return payload

    @staticmethod
    def _to_openai_message(message: LLMMessage) -> dict[str, Any]:
        """Translate one message, including tool calls and tool results, to the Chat Completions shape."""
        if message.role == "tool":
            return {"role": "tool", "tool_call_id": message.tool_call_id or "", "content": message.content}
        translated: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.tool_calls:
            translated["content"] = message.content or None
            translated["tool_calls"] = [
                {
                    "id": call.id or f"call_{index}",
                    "type": "function",
                    "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                    **call.provider_data,
                }
                for index, call in enumerate(message.tool_calls)
            ]
        return translated

    def _to_response(self, result: dict[str, Any], *, request_id: str | None, latency_ms: float) -> LLMResponse:
        """Normalize a completion while retaining only generic response data."""
        choice = (result.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return LLMResponse(
            content=message.get("content") or None,
            tool_calls=[
                ToolCall(
                    id=raw.get("id") or f"call_{uuid4().hex[:12]}",
                    name=raw["function"]["name"],
                    arguments=self._parse_arguments(raw["function"].get("arguments") or ""),
                    provider_data={"extra_content": raw["extra_content"]} if raw.get("extra_content") else {},
                )
                for raw in message.get("tool_calls") or []
                if (raw.get("function") or {}).get("name")
            ],
            provider=self.name,
            model=str(result.get("model") or self._default_model),
            usage=self._to_usage(result.get("usage") or {}),
            finish_reason=choice.get("finish_reason"),
            latency_ms=latency_ms,
            metadata=ResponseMetadata(request_id=request_id),
        )

    @classmethod
    def _to_usage(cls, usage: dict[str, Any]) -> LLMUsage:
        """Read token counters from a completion or the final stream chunk."""
        input_tokens = cls._as_non_negative_int(usage.get("prompt_tokens"))
        output_tokens = cls._as_non_negative_int(usage.get("completion_tokens"))
        return LLMUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=input_tokens + output_tokens)

    @staticmethod
    def _parse_arguments(raw: str) -> dict[str, Any]:
        """Parse tool arguments JSON; an empty or malformed value becomes an empty object."""
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _as_non_negative_int(value: object) -> int:
        """Normalize optional usage values."""
        return value if isinstance(value, int) and value >= 0 else 0

    def _log_outcome(
        self,
        *,
        request_id: str | None,
        latency_ms: float,
        success: bool,
        error: OpenAICompatibleProviderError | None = None,
    ) -> None:
        """Log safe boundary telemetry without serializing requests or their contents."""
        (self._logger.info if success else self._logger.error)(
            "Generation completed" if success else (
                "Generation failed | provider=%s model=%s request_id=%s error_reason=%s error_status=%s"
            ),
            *(() if success else (self.name, self._default_model, request_id, error.reason if error else None, error.status_code if error else None)),
            extra={
                "provider": self.name,
                "model": self._default_model,
                "request_id": request_id,
                "latency_ms": round(latency_ms, 2),
                "success": success,
                "error_reason": error.reason if error else None,
                "error_status": error.status_code if error else None,
            },
        )

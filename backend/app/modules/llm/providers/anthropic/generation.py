"""Generation adapter translating Setu contracts to and from the Anthropic Messages API."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from time import perf_counter
from typing import Any

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
from app.modules.llm.providers.anthropic.client import AnthropicClient, AnthropicProviderError


class AnthropicGenerationProvider(GenerationProvider):
    """Provider-neutral generation implementation backed by Claude models."""

    def __init__(self, client: AnthropicClient, default_model: str, *, default_max_tokens: int) -> None:
        self._client = client
        self._default_model = default_model
        self._default_max_tokens = default_max_tokens
        self._logger = get_logger(__name__)

    @property
    def name(self) -> str:
        """Return this adapter's stable application-level provider name."""
        return "anthropic"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a complete response from Claude for a Setu request."""
        started_at = perf_counter()
        request_id = request.metadata.request_id
        try:
            result = await self._client.create_message(self._to_payload(request, stream=False))
            latency_ms = (perf_counter() - started_at) * 1000
            response = self._to_response(result, request_id=request_id, latency_ms=latency_ms)
            self._log_outcome(request_id=request_id, latency_ms=latency_ms, success=True)
            return response
        except AnthropicProviderError as error:
            self._log_outcome(request_id=request_id, latency_ms=(perf_counter() - started_at) * 1000, success=False, error=error)
            raise

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        """Yield text deltas as they arrive and each tool call once its input is complete."""
        started_at = perf_counter()
        request_id = request.metadata.request_id
        metadata = ResponseMetadata(request_id=request_id)
        input_tokens = 0
        # Tool-use blocks stream their JSON input in fragments, keyed by content-block index.
        pending_tools: dict[int, dict[str, Any]] = {}
        try:
            async for event in self._client.stream_message(self._to_payload(request, stream=True)):
                event_type = event.get("type")
                if event_type == "message_start":
                    input_tokens = self._as_non_negative_int(event.get("message", {}).get("usage", {}).get("input_tokens"))
                elif event_type == "content_block_start":
                    block = event.get("content_block", {})
                    if block.get("type") == "tool_use":
                        pending_tools[event.get("index", 0)] = {"id": block.get("id"), "name": block.get("name"), "json": []}
                elif event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        yield LLMStreamChunk(content_delta=delta["text"], metadata=metadata)
                    elif delta.get("type") == "input_json_delta" and event.get("index", 0) in pending_tools:
                        pending_tools[event.get("index", 0)]["json"].append(delta.get("partial_json", ""))
                elif event_type == "content_block_stop" and event.get("index", 0) in pending_tools:
                    tool = pending_tools.pop(event.get("index", 0))
                    yield LLMStreamChunk(
                        tool_calls=[ToolCall(id=tool["id"], name=tool["name"], arguments=self._parse_arguments("".join(tool["json"])))],
                        metadata=metadata,
                    )
                elif event_type == "message_delta":
                    output_tokens = self._as_non_negative_int(event.get("usage", {}).get("output_tokens"))
                    yield LLMStreamChunk(
                        finish_reason=event.get("delta", {}).get("stop_reason"),
                        usage=LLMUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=input_tokens + output_tokens),
                        metadata=metadata,
                    )
            self._log_outcome(request_id=request_id, latency_ms=(perf_counter() - started_at) * 1000, success=True)
        except AnthropicProviderError as error:
            self._log_outcome(request_id=request_id, latency_ms=(perf_counter() - started_at) * 1000, success=False, error=error)
            raise

    def _to_payload(self, request: LLMRequest, *, stream: bool) -> dict[str, Any]:
        """Translate prepared messages and tools into a Messages API request body."""
        if request.response_format.type == "structured":
            raise AnthropicProviderError(
                "Structured output is not supported by the Anthropic generation provider.",
                reason="unsupported_response_format",
            )

        system = "\n\n".join(message.content for message in request.messages if message.role == "system")
        payload: dict[str, Any] = {
            "model": self._default_model,
            "max_tokens": request.generation.max_tokens or self._default_max_tokens,
            "messages": self._to_anthropic_messages([message for message in request.messages if message.role != "system"]),
            "stream": stream,
        }
        if system:
            payload["system"] = system
        if request.tools:
            payload["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.input_schema or {"type": "object", "properties": {}},
                }
                for tool in request.tools
            ]
        if request.generation.temperature is not None:
            payload["temperature"] = min(request.generation.temperature, 1.0)
        if request.generation.top_p is not None:
            payload["top_p"] = request.generation.top_p
        if request.generation.stop_sequences:
            payload["stop_sequences"] = request.generation.stop_sequences
        return payload

    @staticmethod
    def _to_anthropic_messages(messages: list[LLMMessage]) -> list[dict[str, Any]]:
        """Convert to content blocks, sending tool results as user turns and merging same-role neighbours."""
        converted: list[dict[str, Any]] = []
        for message in messages:
            if message.role == "tool":
                role, blocks = "user", [{"type": "tool_result", "tool_use_id": message.tool_call_id or "", "content": message.content}]
            else:
                role = message.role
                blocks = [{"type": "text", "text": message.content}] if message.content else []
                blocks += [
                    {"type": "tool_use", "id": call.id or f"call_{index}", "name": call.name, "input": call.arguments}
                    for index, call in enumerate(message.tool_calls)
                ]
            if not blocks:
                continue
            if converted and converted[-1]["role"] == role:
                converted[-1]["content"].extend(blocks)
            else:
                converted.append({"role": role, "content": blocks})
        return converted

    def _to_response(self, result: dict[str, Any], *, request_id: str | None, latency_ms: float) -> LLMResponse:
        """Normalize a Messages API response while retaining only generic response data."""
        blocks = result.get("content") or []
        text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        usage = result.get("usage", {})
        input_tokens = self._as_non_negative_int(usage.get("input_tokens"))
        output_tokens = self._as_non_negative_int(usage.get("output_tokens"))
        return LLMResponse(
            content=text or None,
            tool_calls=[
                ToolCall(id=block.get("id"), name=block["name"], arguments=block.get("input") or {})
                for block in blocks
                if block.get("type") == "tool_use" and block.get("name")
            ],
            provider=self.name,
            model=str(result.get("model") or self._default_model),
            usage=LLMUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=input_tokens + output_tokens),
            finish_reason=result.get("stop_reason"),
            latency_ms=latency_ms,
            metadata=ResponseMetadata(request_id=request_id),
        )

    @staticmethod
    def _parse_arguments(raw: str) -> dict[str, Any]:
        """Parse accumulated tool input JSON; an empty or malformed input becomes an empty object."""
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
        error: AnthropicProviderError | None = None,
    ) -> None:
        """Log safe boundary telemetry without serializing requests or their contents."""
        (self._logger.info if success else self._logger.error)(
            "Anthropic generation completed" if success else (
                "Anthropic generation failed | model=%s request_id=%s error_reason=%s error_status=%s"
            ),
            *(() if success else (self._default_model, request_id, error.reason if error else None, error.status_code if error else None)),
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

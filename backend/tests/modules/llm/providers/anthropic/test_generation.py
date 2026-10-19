"""Mocked unit tests for the Anthropic generation adapter."""

from __future__ import annotations

import json
import unittest
from collections.abc import Callable

import httpx

from app.modules.llm.domain.models import LLMCapability, LLMMessage, LLMRequest, RequestMetadata, ToolCall, ToolDefinition
from app.modules.llm.providers.anthropic.client import AnthropicClient, AnthropicProviderError
from app.modules.llm.providers.anthropic.generation import AnthropicGenerationProvider


def _sse(*events: dict[str, object]) -> bytes:
    return "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events).encode()


class AnthropicGenerationProviderTests(unittest.IsolatedAsyncioTestCase):
    """Verify Messages API translation using in-memory HTTP responses only."""

    def _provider(self, handler: Callable[[httpx.Request], httpx.Response]) -> tuple[AnthropicGenerationProvider, httpx.AsyncClient]:
        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://anthropic.test")
        return AnthropicGenerationProvider(AnthropicClient(http_client), "claude-test", default_max_tokens=1024), http_client

    def _request(self, **changes: object) -> LLMRequest:
        values: dict[str, object] = {
            "capability": LLMCapability.REASONING,
            "messages": [LLMMessage(role="system", content="Be brief."), LLMMessage(role="user", content="Hello")],
            "metadata": RequestMetadata(request_id="req-1"),
        }
        values.update(changes)
        return LLMRequest(**values)

    async def test_payload_translates_system_tools_and_tool_results(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            self.assertEqual(request.url.path, "/v1/messages")
            return httpx.Response(200, json={"model": "claude-test", "content": [{"type": "text", "text": "Hi"}], "stop_reason": "end_turn", "usage": {"input_tokens": 5, "output_tokens": 1}})

        provider, http_client = self._provider(handler)
        calls = [ToolCall(id="toolu_1", name="basics__calculator", arguments={"expression": "1+1"}), ToolCall(id="toolu_2", name="basics__current_time", arguments={})]
        try:
            await provider.generate(self._request(
                messages=[
                    LLMMessage(role="system", content="Be brief."),
                    LLMMessage(role="user", content="1+1 and time?"),
                    LLMMessage(role="assistant", content="", tool_calls=calls),
                    LLMMessage(role="tool", content="2", name="basics__calculator", tool_call_id="toolu_1"),
                    LLMMessage(role="tool", content="noon", name="basics__current_time", tool_call_id="toolu_2"),
                ],
                tools=[ToolDefinition(name="basics__calculator", description="Math", input_schema={"type": "object"})],
            ))
        finally:
            await http_client.aclose()

        self.assertEqual(captured["system"], "Be brief.")
        self.assertEqual(captured["max_tokens"], 1024)
        self.assertEqual(captured["tools"], [{"name": "basics__calculator", "description": "Math", "input_schema": {"type": "object"}}])
        messages = captured["messages"]
        assert isinstance(messages, list)
        self.assertEqual([message["role"] for message in messages], ["user", "assistant", "user"])
        self.assertEqual([block["type"] for block in messages[1]["content"]], ["tool_use", "tool_use"])
        self.assertEqual(messages[2]["content"], [
            {"type": "tool_result", "tool_use_id": "toolu_1", "content": "2"},
            {"type": "tool_result", "tool_use_id": "toolu_2", "content": "noon"},
        ])

    async def test_response_normalization_with_tool_use(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "model": "claude-test",
                "content": [{"type": "text", "text": "Checking."}, {"type": "tool_use", "id": "toolu_9", "name": "basics__get_weather", "input": {"location": "Pune"}}],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 12, "output_tokens": 8},
            })

        provider, http_client = self._provider(handler)
        try:
            response = await provider.generate(self._request())
        finally:
            await http_client.aclose()
        self.assertEqual(response.content, "Checking.")
        self.assertEqual([(call.id, call.name, call.arguments) for call in response.tool_calls], [("toolu_9", "basics__get_weather", {"location": "Pune"})])
        self.assertEqual((response.finish_reason, response.usage.total_tokens), ("tool_use", 20))

    async def test_streaming_emits_text_tool_calls_and_usage(self) -> None:
        body = _sse(
            {"type": "message_start", "message": {"usage": {"input_tokens": 30}}},
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Let me "}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "check."}},
            {"type": "content_block_stop", "index": 0},
            {"type": "content_block_start", "index": 1, "content_block": {"type": "tool_use", "id": "toolu_1", "name": "basics__get_weather", "input": {}}},
            {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": "{\"locat"}},
            {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": "ion\": \"Pune\"}"}},
            {"type": "content_block_stop", "index": 1},
            {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 15}},
            {"type": "message_stop"},
        )
        provider, http_client = self._provider(lambda _: httpx.Response(200, content=body, headers={"content-type": "text/event-stream"}))
        try:
            chunks = [chunk async for chunk in provider.stream(self._request())]
        finally:
            await http_client.aclose()

        self.assertEqual("".join(chunk.content_delta or "" for chunk in chunks), "Let me check.")
        tool_calls = [call for chunk in chunks for call in chunk.tool_calls]
        self.assertEqual([(call.id, call.name, call.arguments) for call in tool_calls], [("toolu_1", "basics__get_weather", {"location": "Pune"})])
        final = chunks[-1]
        self.assertEqual(final.finish_reason, "tool_use")
        self.assertEqual(final.usage.total_tokens if final.usage else None, 45)

    async def test_authentication_failure_keeps_error_type(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}})

        provider, http_client = self._provider(handler)
        try:
            with self.assertRaises(AnthropicProviderError) as error:
                _ = [chunk async for chunk in provider.stream(self._request())]
        finally:
            await http_client.aclose()
        self.assertEqual((error.exception.status_code, error.exception.reason), (401, "authentication_error"))

    async def test_stream_error_event_raises(self) -> None:
        body = _sse({"type": "message_start", "message": {"usage": {}}}, {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}})
        provider, http_client = self._provider(lambda _: httpx.Response(200, content=body))
        try:
            with self.assertRaises(AnthropicProviderError) as error:
                _ = [chunk async for chunk in provider.stream(self._request())]
        finally:
            await http_client.aclose()
        self.assertEqual(error.exception.reason, "overloaded_error")

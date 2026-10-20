"""Mocked unit tests for the OpenAI-compatible (Gemini) generation adapter."""

from __future__ import annotations

import json
import unittest
from collections.abc import Callable

import httpx

from app.modules.llm.domain.models import LLMCapability, LLMMessage, LLMRequest, RequestMetadata, ToolCall, ToolDefinition
from app.modules.llm.providers.openai_compatible.client import OpenAICompatibleClient, OpenAICompatibleProviderError
from app.modules.llm.providers.openai_compatible.generation import OpenAICompatibleGenerationProvider


SIGNATURE = {"extra_content": {"google": {"thought_signature": "sig-1"}}}


def _sse(*chunks: dict[str, object]) -> bytes:
    return ("".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n").encode()


class OpenAICompatibleGenerationProviderTests(unittest.IsolatedAsyncioTestCase):
    """Verify Chat Completions translation using in-memory HTTP responses only."""

    def _provider(self, handler: Callable[[httpx.Request], httpx.Response]) -> tuple[OpenAICompatibleGenerationProvider, httpx.AsyncClient]:
        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://gemini.test/v1beta/openai")
        provider = OpenAICompatibleGenerationProvider(
            OpenAICompatibleClient(http_client), "gemini-test", provider_name="gemini", reasoning_effort="low"
        )
        return provider, http_client

    def _request(self, **changes: object) -> LLMRequest:
        values: dict[str, object] = {
            "capability": LLMCapability.REASONING,
            "messages": [LLMMessage(role="system", content="Be brief."), LLMMessage(role="user", content="Hello")],
            "metadata": RequestMetadata(request_id="req-1"),
        }
        values.update(changes)
        return LLMRequest(**values)

    async def test_payload_translates_tools_and_echoes_thought_signature(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            self.assertEqual(request.url.path, "/v1beta/openai/chat/completions")
            return httpx.Response(200, json={"model": "gemini-test", "choices": [{"message": {"content": "Hi"}, "finish_reason": "stop"}]})

        provider, http_client = self._provider(handler)
        call = ToolCall(id="fc_1", name="basics__calculator", arguments={"expression": "1+1"}, provider_data=SIGNATURE)
        try:
            await provider.generate(self._request(
                messages=[
                    LLMMessage(role="system", content="Be brief."),
                    LLMMessage(role="user", content="1+1?"),
                    LLMMessage(role="assistant", content="", tool_calls=[call]),
                    LLMMessage(role="tool", content="2", name="basics__calculator", tool_call_id="fc_1"),
                ],
                tools=[ToolDefinition(name="basics__calculator", description="Math", input_schema={"type": "object"})],
            ))
        finally:
            await http_client.aclose()

        self.assertEqual((captured["model"], captured["reasoning_effort"]), ("gemini-test", "low"))
        self.assertEqual(captured["tools"], [{"type": "function", "function": {"name": "basics__calculator", "description": "Math", "parameters": {"type": "object"}}}])
        messages = captured["messages"]
        assert isinstance(messages, list)
        self.assertEqual([message["role"] for message in messages], ["system", "user", "assistant", "tool"])
        self.assertEqual(messages[2]["tool_calls"], [{
            "id": "fc_1",
            "type": "function",
            "function": {"name": "basics__calculator", "arguments": "{\"expression\": \"1+1\"}"},
            **SIGNATURE,
        }])
        self.assertEqual(messages[3], {"role": "tool", "tool_call_id": "fc_1", "content": "2"})

    async def test_response_normalization_with_tool_call(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "model": "gemini-test",
                "choices": [{
                    "message": {"content": None, "tool_calls": [{"id": "fc_9", "type": "function", "function": {"name": "basics__get_weather", "arguments": "{\"location\": \"Pune\"}"}, **SIGNATURE}]},
                    "finish_reason": "tool_calls",
                }],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8},
            })

        provider, http_client = self._provider(handler)
        try:
            response = await provider.generate(self._request())
        finally:
            await http_client.aclose()
        self.assertIsNone(response.content)
        self.assertEqual([(call.id, call.name, call.arguments, call.provider_data) for call in response.tool_calls], [("fc_9", "basics__get_weather", {"location": "Pune"}, SIGNATURE)])
        self.assertEqual((response.provider, response.finish_reason, response.usage.total_tokens), ("gemini", "tool_calls", 20))

    async def test_streaming_emits_text_then_assembled_tool_calls_and_usage(self) -> None:
        body = _sse(
            {"choices": [{"index": 0, "delta": {"role": "assistant", "content": "Let me "}}]},
            {"choices": [{"index": 0, "delta": {"content": "check."}}]},
            {"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "id": "fc_1", "type": "function", "function": {"name": "basics__get_weather", "arguments": "{\"locat"}, **SIGNATURE}]}}]},
            {"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "function": {"arguments": "ion\": \"Pune\"}"}}]}, "finish_reason": "tool_calls"}]},
            {"choices": [], "usage": {"prompt_tokens": 30, "completion_tokens": 15}},
        )
        provider, http_client = self._provider(lambda _: httpx.Response(200, content=body, headers={"content-type": "text/event-stream"}))
        try:
            chunks = [chunk async for chunk in provider.stream(self._request())]
        finally:
            await http_client.aclose()

        self.assertEqual("".join(chunk.content_delta or "" for chunk in chunks), "Let me check.")
        tool_calls = [call for chunk in chunks for call in chunk.tool_calls]
        self.assertEqual([(call.id, call.name, call.arguments, call.provider_data) for call in tool_calls], [("fc_1", "basics__get_weather", {"location": "Pune"}, SIGNATURE)])
        final = chunks[-1]
        self.assertEqual(final.finish_reason, "tool_calls")
        self.assertEqual(final.usage.total_tokens if final.usage else None, 45)

    async def test_streaming_assigns_ids_to_tool_calls_without_one(self) -> None:
        body = _sse({"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "function": {"name": "basics__current_time", "arguments": "{}"}}]}, "finish_reason": "tool_calls"}]})
        provider, http_client = self._provider(lambda _: httpx.Response(200, content=body))
        try:
            chunks = [chunk async for chunk in provider.stream(self._request())]
        finally:
            await http_client.aclose()
        (call,) = [call for chunk in chunks for call in chunk.tool_calls]
        self.assertTrue(call.id and call.id.startswith("call_"))

    async def test_rate_limit_keeps_provider_status(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json=[{"error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}}])

        provider, http_client = self._provider(handler)
        try:
            with self.assertRaises(OpenAICompatibleProviderError) as error:
                _ = [chunk async for chunk in provider.stream(self._request())]
        finally:
            await http_client.aclose()
        self.assertEqual((error.exception.status_code, error.exception.reason), (429, "RESOURCE_EXHAUSTED"))

"""Mocked unit tests for the Ollama generation adapter."""

from __future__ import annotations

import json
import unittest
from collections.abc import Callable
from unittest.mock import Mock

import httpx

from app.modules.llm.domain.models import (
    GenerationConfig,
    LLMCapability,
    LLMMessage,
    LLMRequest,
    RequestMetadata,
    ResponseFormat,
)
from app.modules.llm.providers.ollama.client import OllamaClient, OllamaProviderError
from app.modules.llm.providers.ollama.generation import OllamaGenerationProvider


class OllamaGenerationProviderTests(unittest.IsolatedAsyncioTestCase):
    """Verify translation and errors with in-memory HTTP responses only."""

    def _provider(self, handler: Callable[[httpx.Request], httpx.Response]) -> tuple[OllamaGenerationProvider, httpx.AsyncClient]:
        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://ollama.test")
        provider = OllamaGenerationProvider(OllamaClient(http_client), "qwen2.5:3b")
        return provider, http_client

    def _request(self, **changes: object) -> LLMRequest:
        values: dict[str, object] = {
            "capability": LLMCapability.GENERATION,
            "messages": [LLMMessage(role="user", content="Hello")],
            "metadata": RequestMetadata(request_id="req-123"),
        }
        values.update(changes)
        return LLMRequest(**values)

    async def test_successful_generation_translates_request(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            self.assertEqual(request.url.path, "/api/chat")
            self.assertEqual(body["model"], "qwen2.5:3b")
            self.assertFalse(body["stream"])
            self.assertEqual(body["messages"], [{"role": "user", "content": "Hello"}])
            return httpx.Response(200, json={"model": "qwen2.5:3b", "message": {"content": "Hi"}})

        provider, http_client = self._provider(handler)
        try:
            self.assertEqual((await provider.generate(self._request())).content, "Hi")
        finally:
            await http_client.aclose()

    async def test_generation_configuration_translation(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            self.assertEqual(body["options"], {"temperature": 0.2, "num_predict": 32, "top_p": 0.9, "stop": ["END"]})
            self.assertEqual(body["format"], "json")
            return httpx.Response(200, json={"message": {"content": "{}"}})

        provider, http_client = self._provider(handler)
        try:
            request = self._request(generation=GenerationConfig(temperature=0.2, max_tokens=32, top_p=0.9, stop_sequences=["END"]), response_format=ResponseFormat(type="json"))
            await provider.generate(request)
        finally:
            await http_client.aclose()

    async def test_response_normalization(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"model": "qwen2.5:3b", "message": {"content": "Hi"}, "done_reason": "stop", "prompt_eval_count": 3, "eval_count": 2})

        provider, http_client = self._provider(handler)
        try:
            response = await provider.generate(self._request())
        finally:
            await http_client.aclose()
        self.assertEqual(response.provider, "ollama")
        self.assertEqual(response.model, "qwen2.5:3b")
        self.assertEqual(response.usage.total_tokens, 5)
        self.assertEqual(response.finish_reason, "stop")
        self.assertEqual(response.metadata.request_id, "req-123")
        self.assertIsNotNone(response.latency_ms)

    async def test_generate_wraps_http_failure(self) -> None:
        provider, http_client = self._provider(lambda _: httpx.Response(503))
        logger = Mock()
        provider._logger = logger
        try:
            with self.assertRaises(OllamaProviderError) as error:
                await provider.generate(self._request())
        finally:
            await http_client.aclose()
        self.assertEqual(error.exception.status_code, 503)
        logger.error.assert_called_once()
        _, arguments, keyword_arguments = logger.error.mock_calls[0]
        self.assertIn("error_reason=%s", arguments[0])
        self.assertEqual(arguments[4], "http_status_error")
        self.assertEqual(arguments[5], 503)
        self.assertEqual(arguments[6], "OllamaProviderError")
        self.assertEqual(keyword_arguments["extra"]["error_reason"], "http_status_error")
        self.assertEqual(keyword_arguments["extra"]["error_status"], 503)

    async def test_generate_wraps_connection_failure(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("unavailable", request=request)

        provider, http_client = self._provider(handler)
        try:
            with self.assertRaises(OllamaProviderError) as error:
                await provider.generate(self._request())
        finally:
            await http_client.aclose()
        self.assertEqual(error.exception.reason, "ConnectError")

    async def test_streaming_success(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b'{"message":{"content":"Hi"},"done":false}\n{"message":{"content":""},"done":true,"done_reason":"stop"}\n')

        provider, http_client = self._provider(handler)
        try:
            chunks = [chunk async for chunk in provider.stream(self._request())]
        finally:
            await http_client.aclose()
        self.assertEqual(chunks[0].content_delta, "Hi")
        self.assertEqual(chunks[1].finish_reason, "stop")

    async def test_streaming_wraps_http_failure(self) -> None:
        provider, http_client = self._provider(lambda _: httpx.Response(502))
        try:
            with self.assertRaises(OllamaProviderError) as error:
                _ = [chunk async for chunk in provider.stream(self._request())]
        finally:
            await http_client.aclose()
        self.assertEqual(error.exception.status_code, 502)

    async def test_structured_output_is_rejected(self) -> None:
        provider, http_client = self._provider(lambda _: self.fail("HTTP should not be called"))
        try:
            with self.assertRaises(OllamaProviderError) as error:
                await provider.generate(self._request(response_format=ResponseFormat(type="structured", schema_definition={"type": "object"})))
        finally:
            await http_client.aclose()
        self.assertEqual(error.exception.reason, "unsupported_response_format")

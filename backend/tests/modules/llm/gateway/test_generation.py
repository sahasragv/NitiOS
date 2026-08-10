"""Unit tests for the provider-neutral generation gateway."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator

from app.modules.llm.domain.interfaces import GenerationProvider
from app.modules.llm.domain.models import (
    LLMCapability,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    RequestMetadata,
    ResponseMetadata,
)
from app.modules.llm.gateway.generation import LLMGateway


class FakeGenerationProvider(GenerationProvider):
    """In-memory provider used to verify gateway delegation behavior."""

    def __init__(self, *, error: Exception | None = None, stream_error: Exception | None = None) -> None:
        self.error = error
        self.stream_error = stream_error
        self.last_request: LLMRequest | None = None

    @property
    def name(self) -> str:
        return "fake"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.last_request = request
        if self.error:
            raise self.error
        return LLMResponse(content="complete", provider=self.name, model="fake-model", metadata=ResponseMetadata(request_id=request.metadata.request_id))

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        self.last_request = request
        if self.stream_error:
            raise self.stream_error
        yield LLMStreamChunk(content_delta="part", metadata=ResponseMetadata(request_id=request.metadata.request_id))
        yield LLMStreamChunk(finish_reason="stop", metadata=ResponseMetadata(request_id=request.metadata.request_id))


class LLMGatewayTests(unittest.IsolatedAsyncioTestCase):
    """Verify gateway behavior without depending on an HTTP provider."""

    @staticmethod
    def _request() -> LLMRequest:
        return LLMRequest(
            capability=LLMCapability.GENERATION,
            messages=[LLMMessage(role="user", content="Hello")],
            metadata=RequestMetadata(request_id="request-123"),
        )

    async def test_generate_returns_provider_response_and_preserves_request_id(self) -> None:
        provider = FakeGenerationProvider()
        response = await LLMGateway(provider).generate(self._request())
        self.assertEqual(response.content, "complete")
        self.assertEqual(response.metadata.request_id, "request-123")
        self.assertEqual(provider.last_request.metadata.request_id if provider.last_request else None, "request-123")

    async def test_generate_propagates_provider_failure(self) -> None:
        failure = RuntimeError("provider failure")
        with self.assertRaisesRegex(RuntimeError, "provider failure"):
            await LLMGateway(FakeGenerationProvider(error=failure)).generate(self._request())

    async def test_stream_yields_provider_chunks_without_buffering(self) -> None:
        provider = FakeGenerationProvider()
        chunks = [chunk async for chunk in LLMGateway(provider).stream(self._request())]
        self.assertEqual([chunk.content_delta for chunk in chunks], ["part", None])
        self.assertEqual(chunks[0].metadata.request_id, "request-123")

    async def test_stream_propagates_provider_failure(self) -> None:
        failure = RuntimeError("stream failure")
        with self.assertRaisesRegex(RuntimeError, "stream failure"):
            _ = [chunk async for chunk in LLMGateway(FakeGenerationProvider(stream_error=failure)).stream(self._request())]

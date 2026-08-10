"""Unit tests for the LLM generation application service."""

from __future__ import annotations

import unittest

from app.modules.llm.application.generation import (
    GenerateLLMCommand,
    LLMGenerationFailedError,
    LLMGenerationRequestError,
    LLMGenerationService,
)
from app.modules.llm.domain.interfaces import LLMProviderInfrastructureError
from app.modules.llm.domain.models import LLMCapability, LLMMessage, LLMResponse
from app.modules.llm.gateway.generation import LLMGatewayRequestError


class FakeGateway:
    """Minimal gateway double used to inspect domain request construction."""

    def __init__(self, error: Exception | None = None) -> None:
        self.request = None
        self.error = error

    async def generate(self, request: object) -> LLMResponse:
        self.request = request
        if self.error:
            raise self.error
        request_id = getattr(getattr(request, "metadata"), "request_id")
        return LLMResponse(content="complete", provider="fake", model="fake", metadata={"request_id": request_id})


class LLMGenerationServiceTests(unittest.IsolatedAsyncioTestCase):
    """Verify use-case request construction without an HTTP provider."""

    async def test_generate_creates_a_request_id_when_missing(self) -> None:
        gateway = FakeGateway()
        service = LLMGenerationService(gateway)  # type: ignore[arg-type]
        result = await service.generate(GenerateLLMCommand(capability=LLMCapability.GENERATION, messages=[LLMMessage(role="user", content="Hello")]))
        self.assertTrue(result.request_id)
        self.assertEqual(getattr(getattr(gateway.request, "metadata"), "request_id"), result.request_id)

    async def test_invalid_generation_request_maps_to_422_error(self) -> None:
        service = LLMGenerationService(FakeGateway(LLMGatewayRequestError("Messages are invalid")))  # type: ignore[arg-type]
        with self.assertRaises(LLMGenerationRequestError) as error:
            await service.generate(GenerateLLMCommand(capability=LLMCapability.GENERATION, messages=[LLMMessage(role="user", content="Hello")]))
        self.assertEqual(error.exception.status_code, 422)

    async def test_expected_provider_failure_maps_to_502_error(self) -> None:
        service = LLMGenerationService(FakeGateway(LLMProviderInfrastructureError("Provider unavailable")))  # type: ignore[arg-type]
        with self.assertRaises(LLMGenerationFailedError) as error:
            await service.generate(GenerateLLMCommand(capability=LLMCapability.GENERATION, messages=[LLMMessage(role="user", content="Hello")]))
        self.assertEqual(error.exception.status_code, 502)

    async def test_unexpected_programming_error_propagates_unchanged(self) -> None:
        service = LLMGenerationService(FakeGateway(TypeError("unexpected type")))  # type: ignore[arg-type]
        with self.assertRaisesRegex(TypeError, "unexpected type"):
            await service.generate(GenerateLLMCommand(capability=LLMCapability.GENERATION, messages=[LLMMessage(role="user", content="Hello")]))

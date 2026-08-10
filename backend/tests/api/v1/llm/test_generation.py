"""Endpoint tests using a fake application service, with no provider dependency."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.api.v1.llm.dependencies import get_llm_generation_service
from app.main import app
from app.modules.llm.application.generation import GenerateLLMResult, LLMGenerationFailedError
from app.modules.llm.domain.models import LLMUsage


class FakeGenerationService:
    """Record API commands and return controlled application outcomes."""

    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.command = None

    async def generate(self, command: object) -> GenerateLLMResult:
        self.command = command
        if self.error:
            raise self.error
        request_id = getattr(command, "request_id") or "generated-request-id"
        return GenerateLLMResult(content="complete", finish_reason="stop", usage=LLMUsage(input_tokens=2, output_tokens=1, total_tokens=3), request_id=request_id)


class LLMGenerateEndpointTests(unittest.TestCase):
    """Verify controller mapping without contacting Ollama."""

    def setUp(self) -> None:
        self.service = FakeGenerationService()
        app.dependency_overrides[get_llm_generation_service] = lambda: self.service
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()

    def test_successful_post_invokes_application_service(self) -> None:
        response = self.client.post("/api/v1/llm/generate", headers={"X-Request-ID": "request-42"}, json={"capability": "generation", "messages": [{"role": "user", "content": "Hello"}]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["request_id"], "request-42")
        self.assertEqual(getattr(self.service.command, "request_id"), "request-42")

    def test_invalid_request_returns_validation_error(self) -> None:
        response = self.client.post("/api/v1/llm/generate", json={"capability": "generation", "messages": []})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "REQUEST_VALIDATION_ERROR")

    def test_application_failure_maps_to_http_response(self) -> None:
        self.service.error = LLMGenerationFailedError()
        response = self.client.post("/api/v1/llm/generate", json={"capability": "generation", "messages": [{"role": "user", "content": "Hello"}]})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"]["code"], "LLM_GENERATION_FAILED")

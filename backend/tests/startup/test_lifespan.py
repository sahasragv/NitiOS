"""Tests for lifespan-managed Ollama HTTP dependency wiring."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx
from fastapi import FastAPI
from pydantic import ValidationError

from app.core.settings import Settings, settings
from app.startup.lifespan import lifespan


class LifespanTests(unittest.IsolatedAsyncioTestCase):
    """Verify that one configured shared client is injected into the Ollama adapter."""

    async def test_ollama_client_receives_shared_client_with_configured_timeout(self) -> None:
        app = FastAPI()
        shared_http_client = Mock()
        shared_http_client.aclose = AsyncMock()

        with patch("app.startup.lifespan.httpx.AsyncClient", return_value=shared_http_client) as create_client:
            async with lifespan(app):
                create_client.assert_called_once()
                _, kwargs = create_client.call_args
                timeout = kwargs["timeout"]
                self.assertIsInstance(timeout, httpx.Timeout)
                self.assertEqual(timeout.connect, settings.OLLAMA_TIMEOUT_SECONDS)
                self.assertEqual(timeout.read, settings.OLLAMA_TIMEOUT_SECONDS)
                self.assertEqual(timeout.write, settings.OLLAMA_TIMEOUT_SECONDS)
                self.assertEqual(timeout.pool, settings.OLLAMA_TIMEOUT_SECONDS)

                service = app.state.llm_generation_service
                injected_client = service._gateway._provider._client._client
                self.assertIs(injected_client, shared_http_client)

        shared_http_client.aclose.assert_awaited_once()

    def test_ollama_timeout_setting_must_be_positive(self) -> None:
        """Reject invalid timeout configuration before application startup."""
        with self.assertRaises(ValidationError):
            Settings(OLLAMA_TIMEOUT_SECONDS=0)

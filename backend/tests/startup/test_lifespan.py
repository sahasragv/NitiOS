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

        tool_hub = Mock()
        tool_hub.connect = AsyncMock()
        tool_hub.aclose = AsyncMock()

        with (
            patch("app.startup.lifespan.httpx.AsyncClient", return_value=shared_http_client) as create_client,
            patch("app.startup.lifespan.MCPToolHub", return_value=tool_hub),
        ):
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

                self.assertIs(app.state.tool_executor, tool_hub)
                self.assertIs(app.state.chat_agent_service._gateway, service._gateway)
                tool_hub.connect.assert_awaited_once()

        shared_http_client.aclose.assert_awaited_once()
        tool_hub.aclose.assert_awaited_once()

    def test_ollama_timeout_setting_must_be_positive(self) -> None:
        """Reject invalid timeout configuration before application startup."""
        with self.assertRaises(ValidationError):
            Settings(OLLAMA_TIMEOUT_SECONDS=0)


class ProviderSelectionTests(unittest.TestCase):
    """Verify the configured LLM provider is built, with a safe fallback."""

    def test_selects_anthropic_when_configured_with_key(self) -> None:
        from pydantic import SecretStr

        from app.modules.llm.providers.anthropic.generation import AnthropicGenerationProvider
        from app.startup.lifespan import _create_generation_provider

        with patch("app.startup.lifespan.settings", settings.model_copy(update={"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": SecretStr("sk-test")})):
            provider, http_client = _create_generation_provider()
        self.assertIsInstance(provider, AnthropicGenerationProvider)
        self.assertEqual(http_client.headers["x-api-key"], "sk-test")
        self.assertEqual(http_client.headers["anthropic-version"], "2023-06-01")

    def test_falls_back_to_ollama_without_key(self) -> None:
        from app.modules.llm.providers.ollama.generation import OllamaGenerationProvider
        from app.startup.lifespan import _create_generation_provider

        with patch("app.startup.lifespan.settings", settings.model_copy(update={"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": None})):
            provider, _ = _create_generation_provider()
        self.assertIsInstance(provider, OllamaGenerationProvider)

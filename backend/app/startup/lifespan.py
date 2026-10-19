"""Application lifespan composition for the Setu backend."""

import os
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from dotenv import dotenv_values
from fastapi import FastAPI
import httpx

from app.core.logging import get_logger
from app.core.settings import settings
from app.modules.agent.application.chat import ChatAgentService
from app.modules.agent.application.title import ConversationTitleService
from app.modules.llm.domain.interfaces import GenerationProvider
from app.modules.llm.application.generation import LLMGenerationService
from app.modules.llm.gateway.generation import LLMGateway
from app.modules.llm.providers.anthropic.client import AnthropicClient, create_anthropic_http_client
from app.modules.llm.providers.anthropic.generation import AnthropicGenerationProvider
from app.modules.llm.providers.ollama.client import OllamaClient
from app.modules.llm.providers.ollama.generation import OllamaGenerationProvider
from app.modules.tools.infrastructure.mcp_config import load_mcp_server_configs
from app.modules.tools.infrastructure.mcp_hub import MCPToolHub


_logger = get_logger(__name__)


def _environment() -> dict[str, str | None]:
    """Merge ``backend/.env`` with process variables, which take precedence, for MCP config."""
    env_file = settings.model_config.get("env_file")
    file_values = dotenv_values(env_file) if env_file else {}
    return {**file_values, **os.environ}


def _create_generation_provider() -> tuple[GenerationProvider, httpx.AsyncClient]:
    """Build the configured provider and the shared HTTP client it owns."""
    api_key = settings.ANTHROPIC_API_KEY.get_secret_value() if settings.ANTHROPIC_API_KEY else ""
    if settings.LLM_PROVIDER == "anthropic":
        if api_key:
            http_client = create_anthropic_http_client(
                base_url=settings.ANTHROPIC_BASE_URL,
                api_key=api_key,
                timeout_seconds=settings.ANTHROPIC_TIMEOUT_SECONDS,
            )
            provider = AnthropicGenerationProvider(
                AnthropicClient(http_client),
                settings.ANTHROPIC_MODEL,
                default_max_tokens=settings.ANTHROPIC_MAX_TOKENS,
            )
            _logger.info("LLM provider selected | provider=anthropic model=%s", settings.ANTHROPIC_MODEL)
            return provider, http_client
        _logger.warning("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set; falling back to Ollama.")

    timeout = httpx.Timeout(settings.OLLAMA_TIMEOUT_SECONDS)
    http_client = httpx.AsyncClient(base_url=settings.OLLAMA_BASE_URL, timeout=timeout)
    _logger.info("LLM provider selected | provider=ollama model=%s", settings.OLLAMA_DEFAULT_MODEL)
    return OllamaGenerationProvider(OllamaClient(http_client), settings.OLLAMA_DEFAULT_MODEL), http_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create shared clients and services at startup and close them at shutdown."""
    provider, http_client = _create_generation_provider()
    gateway = LLMGateway(provider)
    app.state.llm_generation_service = LLMGenerationService(gateway)
    app.state.title_service = ConversationTitleService(gateway)
    app.state.model_info = {
        "provider": provider.name,
        "model": settings.ANTHROPIC_MODEL if provider.name == "anthropic" else settings.OLLAMA_DEFAULT_MODEL,
    }

    tool_hub = MCPToolHub(
        load_mcp_server_configs(settings.MCP_CONFIG_PATH, _environment()),
        timeout_seconds=settings.MCP_TIMEOUT_SECONDS,
    )
    await tool_hub.connect()
    app.state.tool_executor = tool_hub
    app.state.chat_agent_service = ChatAgentService(gateway, tool_hub, max_steps=settings.AGENT_MAX_STEPS)
    try:
        yield
    finally:
        await tool_hub.aclose()
        await http_client.aclose()


def get_lifespan() -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """Return the lifespan context manager used by the application factory."""
    return lifespan

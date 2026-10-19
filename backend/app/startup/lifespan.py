"""Application lifespan composition for the NitiOS backend."""

import os
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from dotenv import dotenv_values
from fastapi import FastAPI
import httpx

from app.core.settings import settings
from app.modules.agent.application.chat import ChatAgentService
from app.modules.llm.application.generation import LLMGenerationService
from app.modules.llm.gateway.generation import LLMGateway
from app.modules.llm.providers.ollama.client import OllamaClient
from app.modules.llm.providers.ollama.generation import OllamaGenerationProvider
from app.modules.tools.infrastructure.mcp_config import load_mcp_server_configs
from app.modules.tools.infrastructure.mcp_hub import MCPToolHub


def _environment() -> dict[str, str | None]:
    """Merge ``backend/.env`` with process variables, which take precedence, for MCP config."""
    env_file = settings.model_config.get("env_file")
    file_values = dotenv_values(env_file) if env_file else {}
    return {**file_values, **os.environ}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create shared clients and services at startup and close them at shutdown."""
    timeout = httpx.Timeout(settings.OLLAMA_TIMEOUT_SECONDS)
    http_client = httpx.AsyncClient(base_url=settings.OLLAMA_BASE_URL, timeout=timeout)
    ollama_client = OllamaClient(http_client)
    provider = OllamaGenerationProvider(ollama_client, settings.OLLAMA_DEFAULT_MODEL)
    gateway = LLMGateway(provider)
    app.state.llm_generation_service = LLMGenerationService(gateway)

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

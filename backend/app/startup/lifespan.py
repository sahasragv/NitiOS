"""Application lifespan composition for the Setu backend."""

import os
import secrets
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from dotenv import dotenv_values
from fastapi import FastAPI
import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import create_engine, create_session_factory, create_tables
from app.core.logging import get_logger
from app.core.settings import settings
from app.modules.accounts.application.auth import AuthService
from app.modules.accounts.application.connections import ConnectionService
from app.modules.accounts.infrastructure.oauth import GitHubOAuthClient, GoogleOAuthClient
from app.modules.accounts.infrastructure.token_cipher import TokenCipher
from app.modules.agent.application.chat import ChatAgentService
from app.modules.agent.application.title import ConversationTitleService
from app.modules.llm.domain.interfaces import GenerationProvider
from app.modules.llm.application.generation import LLMGenerationService
from app.modules.llm.gateway.generation import LLMGateway
from app.modules.llm.providers.anthropic.client import AnthropicClient, create_anthropic_http_client
from app.modules.llm.providers.anthropic.generation import AnthropicGenerationProvider
from app.modules.llm.providers.ollama.client import OllamaClient
from app.modules.llm.providers.ollama.generation import OllamaGenerationProvider
from app.modules.llm.providers.openai_compatible.client import OpenAICompatibleClient, create_openai_compatible_http_client
from app.modules.llm.providers.openai_compatible.generation import OpenAICompatibleGenerationProvider
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

    gemini_key = settings.GEMINI_API_KEY.get_secret_value() if settings.GEMINI_API_KEY else ""
    if settings.LLM_PROVIDER == "gemini":
        if gemini_key:
            http_client = create_openai_compatible_http_client(
                base_url=settings.GEMINI_BASE_URL,
                api_key=gemini_key,
                timeout_seconds=settings.GEMINI_TIMEOUT_SECONDS,
            )
            provider = OpenAICompatibleGenerationProvider(
                OpenAICompatibleClient(http_client),
                settings.GEMINI_MODEL,
                provider_name="gemini",
                reasoning_effort=settings.GEMINI_REASONING_EFFORT or None,
            )
            _logger.info("LLM provider selected | provider=gemini model=%s", settings.GEMINI_MODEL)
            return provider, http_client
        _logger.warning("LLM_PROVIDER=gemini but GEMINI_API_KEY is not set; falling back to Ollama.")

    timeout = httpx.Timeout(settings.OLLAMA_TIMEOUT_SECONDS)
    http_client = httpx.AsyncClient(base_url=settings.OLLAMA_BASE_URL, timeout=timeout)
    _logger.info("LLM provider selected | provider=ollama model=%s", settings.OLLAMA_DEFAULT_MODEL)
    return OllamaGenerationProvider(OllamaClient(http_client), settings.OLLAMA_DEFAULT_MODEL), http_client


def _secret_key() -> str:
    """Return SECRET_KEY, or a per-process key (connected accounts then need relinking after a restart)."""
    if settings.SECRET_KEY and settings.SECRET_KEY.get_secret_value():
        return settings.SECRET_KEY.get_secret_value()
    _logger.warning("SECRET_KEY is not set; connected accounts will need to be reconnected after every restart.")
    return secrets.token_urlsafe(32)


def _create_account_services(
    session_factory: async_sessionmaker[AsyncSession], http_client: httpx.AsyncClient
) -> tuple[AuthService, ConnectionService]:
    """Build sign-in and connection services; a provider without credentials stays disabled."""
    google_secret = settings.GOOGLE_CLIENT_SECRET.get_secret_value() if settings.GOOGLE_CLIENT_SECRET else ""
    github_secret = settings.GITHUB_CLIENT_SECRET.get_secret_value() if settings.GITHUB_CLIENT_SECRET else ""
    google = (
        GoogleOAuthClient(http_client, client_id=settings.GOOGLE_CLIENT_ID, client_secret=google_secret)
        if settings.GOOGLE_CLIENT_ID and google_secret
        else None
    )
    github = (
        GitHubOAuthClient(http_client, client_id=settings.GITHUB_CLIENT_ID, client_secret=github_secret, scopes=settings.GITHUB_OAUTH_SCOPES)
        if settings.GITHUB_CLIENT_ID and github_secret
        else None
    )
    if google is None:
        _logger.warning("Google sign-in is not configured; set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")
    if github is None:
        _logger.info("GitHub connection is not configured; set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET to enable it.")
    auth = AuthService(
        session_factory,
        google,
        session_ttl_seconds=settings.SESSION_TTL_DAYS * 86400,
        allowed_emails=settings.ALLOWED_EMAILS,
    )
    return auth, ConnectionService(session_factory, TokenCipher(_secret_key()), github)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create shared clients and services at startup and close them at shutdown."""
    engine = create_engine(settings.DATABASE_URL)
    await create_tables(engine)
    # Shared by OAuth exchanges and per-user integration tools such as GitHub.
    integration_http_client = httpx.AsyncClient(timeout=httpx.Timeout(20.0))
    app.state.integration_http_client = integration_http_client
    app.state.auth_service, app.state.connection_service = _create_account_services(
        create_session_factory(engine), integration_http_client
    )

    provider, http_client = _create_generation_provider()
    gateway = LLMGateway(provider)
    app.state.llm_generation_service = LLMGenerationService(gateway)
    app.state.title_service = ConversationTitleService(gateway)
    models = {"anthropic": settings.ANTHROPIC_MODEL, "gemini": settings.GEMINI_MODEL}
    app.state.model_info = {"provider": provider.name, "model": models.get(provider.name, settings.OLLAMA_DEFAULT_MODEL)}

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
        await integration_http_client.aclose()
        await engine.dispose()


def get_lifespan() -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """Return the lifespan context manager used by the application factory."""
    return lifespan

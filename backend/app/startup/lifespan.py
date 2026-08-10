"""Application lifespan composition for the NitiOS backend."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI
import httpx

from app.core.settings import settings
from app.modules.llm.application.generation import LLMGenerationService
from app.modules.llm.gateway.generation import LLMGateway
from app.modules.llm.providers.ollama.client import OllamaClient
from app.modules.llm.providers.ollama.generation import OllamaGenerationProvider


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle placeholders."""
    timeout = httpx.Timeout(settings.OLLAMA_TIMEOUT_SECONDS)
    http_client = httpx.AsyncClient(base_url=settings.OLLAMA_BASE_URL, timeout=timeout)
    ollama_client = OllamaClient(http_client)
    provider = OllamaGenerationProvider(ollama_client, settings.OLLAMA_DEFAULT_MODEL)
    app.state.llm_generation_service = LLMGenerationService(LLMGateway(provider))
    try:
        yield
    finally:
        await http_client.aclose()


def get_lifespan() -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """Return the lifespan context manager used by the application factory."""
    return lifespan

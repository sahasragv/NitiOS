"""Abstract provider boundary for LLM infrastructure."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.modules.llm.domain.models import (
    EmbeddingRequest,
    EmbeddingResponse,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
)


class LLMProviderInfrastructureError(Exception):
    """Expected provider communication failure safe for application-layer handling."""


class GenerationProvider(ABC):
    """Contract for provider adapters that support text generation."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable provider identifier used by the application."""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Execute a non-streaming generation request."""

    @abstractmethod
    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        """Yield normalized response chunks for a streaming generation request."""


class EmbeddingProvider(ABC):
    """Contract for provider adapters that support text embeddings."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable provider identifier used by the application."""

    @abstractmethod
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Create embeddings for the supplied text inputs."""

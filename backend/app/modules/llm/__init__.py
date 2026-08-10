"""Provider-neutral LLM domain contracts for NitiOS."""

from app.modules.llm.domain.interfaces import EmbeddingProvider, GenerationProvider, LLMProviderInfrastructureError
from app.modules.llm.domain.models import (
    EmbeddingRequest,
    EmbeddingResponse,
    GenerationConfig,
    LLMCapability,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    LLMUsage,
    RequestMetadata,
    ResponseFormat,
    ResponseMetadata,
)

__all__ = [
    "EmbeddingProvider",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "GenerationConfig",
    "GenerationProvider",
    "LLMCapability",
    "LLMProviderInfrastructureError",
    "LLMRequest",
    "LLMResponse",
    "LLMStreamChunk",
    "LLMUsage",
    "RequestMetadata",
    "ResponseFormat",
    "ResponseMetadata",
]

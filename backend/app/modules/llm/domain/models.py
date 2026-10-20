"""Provider-neutral, strongly typed contracts for LLM interactions."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LLMCapability(str, Enum):
    """The high-level operation a language model is expected to perform."""

    REASONING = "reasoning"
    GENERATION = "generation"
    SUMMARIZATION = "summarization"
    CLASSIFICATION = "classification"


class ToolDefinition(BaseModel):
    """A provider-independent function tool made available to a request."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """A tool invocation requested by a model response."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    provider_data: dict[str, Any] = Field(default_factory=dict)
    """Opaque provider fields that must be echoed back with the call, such as Gemini's thought signature."""


class LLMMessage(BaseModel):
    """A role-labelled message in an LLM conversation.

    Assistant messages carry ``tool_calls`` when the model requested tools, and
    ``tool`` messages carry the result for the call named by ``name``.
    """

    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class ToolCallDelta(BaseModel):
    """A partial tool invocation emitted during streamed generation."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    name: str | None = None
    arguments_delta: str | None = None


class GenerationConfig(BaseModel):
    """Optional, provider-neutral controls for generated output."""

    model_config = ConfigDict(extra="forbid")

    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0)
    top_p: float | None = Field(default=None, gt=0, le=1)
    stop_sequences: list[str] = Field(default_factory=list)


class ResponseFormat(BaseModel):
    """Desired response representation, extensible to future structured output."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["text", "json", "structured"] = "text"
    schema_definition: dict[str, Any] | None = None

    @model_validator(mode="after")
    def require_schema_for_structured_output(self) -> "ResponseFormat":
        """Require a schema only when explicitly requesting structured output."""
        if self.type == "structured" and self.schema_definition is None:
            raise ValueError("schema_definition is required when type is 'structured'.")
        return self


class RequestMetadata(BaseModel):
    """Application-level context that accompanies an LLM request."""

    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class ResponseMetadata(BaseModel):
    """Application-level metadata returned with an LLM response."""

    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    warnings: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class LLMUsage(BaseModel):
    """Provider-neutral token accounting for a completed operation."""

    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class LLMRequest(BaseModel):
    """A complete, provider-agnostic request for language-model work."""

    model_config = ConfigDict(extra="forbid")

    capability: LLMCapability
    messages: list[LLMMessage] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    tools: list[ToolDefinition] = Field(default_factory=list)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    response_format: ResponseFormat = Field(default_factory=ResponseFormat)
    metadata: RequestMetadata = Field(default_factory=RequestMetadata)


class LLMResponse(BaseModel):
    """A normalized result produced by an LLM provider."""

    model_config = ConfigDict(extra="forbid")

    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    provider: str
    model: str
    usage: LLMUsage = Field(default_factory=LLMUsage)
    finish_reason: str | None = None
    latency_ms: float | None = Field(default=None, ge=0)
    metadata: ResponseMetadata = Field(default_factory=ResponseMetadata)


class LLMStreamChunk(BaseModel):
    """A provider-neutral incremental update from a streamed generation."""

    model_config = ConfigDict(extra="forbid")

    content_delta: str | None = None
    tool_call_delta: ToolCallDelta | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    """Complete tool calls, for providers that emit each call whole rather than as deltas."""
    finish_reason: str | None = None
    usage: LLMUsage | None = None
    """Token usage, typically present only on the final chunk."""
    metadata: ResponseMetadata = Field(default_factory=ResponseMetadata)


class EmbeddingRequest(BaseModel):
    """A provider-neutral request to convert one or more texts into vectors."""

    model_config = ConfigDict(extra="forbid")

    inputs: list[str] = Field(min_length=1)
    metadata: RequestMetadata = Field(default_factory=RequestMetadata)


class EmbeddingResponse(BaseModel):
    """Normalized vector output for an embedding operation."""

    model_config = ConfigDict(extra="forbid")

    embeddings: list[list[float]]
    provider: str
    model: str
    usage: LLMUsage = Field(default_factory=LLMUsage)
    metadata: ResponseMetadata = Field(default_factory=ResponseMetadata)

"""HTTP-specific DTOs for the LLM generation endpoint."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class GenerateMessageDTO(BaseModel):
    """A client-supplied conversation message."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1)
    name: str | None = None
    tool_call_id: str | None = None


class GenerationConfigDTO(BaseModel):
    """HTTP controls for provider-neutral generated output."""

    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0)
    top_p: float | None = Field(default=None, gt=0, le=1)
    stop_sequences: list[str] = Field(default_factory=list)


class ResponseFormatDTO(BaseModel):
    """HTTP representation of the desired output format."""

    type: Literal["text", "json", "structured"] = "text"
    schema_definition: dict[str, Any] | None = None

    @model_validator(mode="after")
    def require_schema_for_structured_output(self) -> "ResponseFormatDTO":
        """Reject structured format requests that omit their schema."""
        if self.type == "structured" and self.schema_definition is None:
            raise ValueError("schema_definition is required when type is 'structured'.")
        return self


class GenerateRequestDTO(BaseModel):
    """Public request body for one LLM generation operation."""

    capability: Literal["reasoning", "generation", "summarization", "classification"]
    messages: list[GenerateMessageDTO] = Field(min_length=1)
    generation: GenerationConfigDTO | None = None
    response_format: ResponseFormatDTO | None = None


class UsageDTO(BaseModel):
    """Public token accounting returned by a generation operation."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


class GenerateResponseDTO(BaseModel):
    """Public generation result without provider or model details."""

    content: str | None = None
    finish_reason: str | None = None
    usage: UsageDTO
    request_id: str

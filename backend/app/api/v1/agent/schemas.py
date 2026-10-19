"""HTTP-specific DTOs for the agent chat endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessageDTO(BaseModel):
    """One prior or current message in the conversation, as sent by the client."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequestDTO(BaseModel):
    """Public request body for one chat turn; the last message should be from the user."""

    messages: list[ChatMessageDTO] = Field(min_length=1)


class ToolInvocationDTO(BaseModel):
    """A tool the assistant used while answering."""

    name: str
    arguments: dict[str, Any]
    output: str
    is_error: bool


class ChatUsageDTO(BaseModel):
    """Token accounting summed across every model call in the turn."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


class ChatResponseDTO(BaseModel):
    """Public chat result."""

    content: str | None = None
    tool_invocations: list[ToolInvocationDTO]
    finish_reason: str | None = None
    usage: ChatUsageDTO
    steps: int
    request_id: str


class ToolDTO(BaseModel):
    """A tool currently available to the assistant."""

    name: str
    description: str | None = None
    input_schema: dict[str, Any]

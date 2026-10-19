"""Provider-neutral results of tool execution."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolResult(BaseModel):
    """Normalized text output from one tool execution."""

    model_config = ConfigDict(extra="forbid")

    output: str
    is_error: bool = False


class ToolInvocation(BaseModel):
    """A record of a tool the agent called while answering, safe to show to users."""

    model_config = ConfigDict(extra="forbid")

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    output: str
    is_error: bool = False

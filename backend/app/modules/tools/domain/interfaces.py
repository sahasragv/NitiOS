"""Abstract boundary between the agent and whatever executes its tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.modules.llm.domain.models import ToolDefinition
from app.modules.tools.domain.models import ToolResult


class ToolExecutor(ABC):
    """Contract for components that expose tools to an LLM and execute its calls."""

    @abstractmethod
    def list_tools(self) -> list[ToolDefinition]:
        """Return every tool currently available to the model."""

    @abstractmethod
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute ``name`` and return its output; failures are reported as error results."""

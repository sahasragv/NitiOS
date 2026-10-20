"""Combine several tool executors into one, such as shared tools plus a user's own."""

from __future__ import annotations

from typing import Any

from app.modules.llm.domain.models import ToolDefinition
from app.modules.tools.domain.interfaces import ToolExecutor
from app.modules.tools.domain.models import ToolResult


class CompositeToolExecutor(ToolExecutor):
    """Expose every tool of ``executors`` and route each call to the executor that owns it."""

    def __init__(self, executors: list[ToolExecutor]) -> None:
        self._executors = executors

    def list_tools(self) -> list[ToolDefinition]:
        """Return the tools of every executor, in order."""
        return [tool for executor in self._executors for tool in executor.list_tools()]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Run ``name`` on the first executor that lists it."""
        for executor in self._executors:
            if any(tool.name == name for tool in executor.list_tools()):
                return await executor.call_tool(name, arguments)
        return ToolResult(output=f"Unknown tool '{name}'.", is_error=True)

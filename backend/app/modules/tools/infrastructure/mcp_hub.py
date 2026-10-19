"""Aggregate tools from many MCP servers behind one ``ToolExecutor``."""

from __future__ import annotations

import re
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, TextContent

from app.core.logging import get_logger
from app.modules.llm.domain.models import ToolDefinition
from app.modules.tools.domain.interfaces import ToolExecutor
from app.modules.tools.domain.models import ToolResult
from app.modules.tools.infrastructure.mcp_config import MCPServerConfig


_BACKEND_DIRECTORY = Path(__file__).resolve().parents[4]
_TOOL_NAME_SEPARATOR = "__"
_MAX_TOOL_NAME_LENGTH = 64
MAX_TOOL_OUTPUT_CHARS = 8000
"""Tool output beyond this length is truncated to protect the model's context window."""


@dataclass(frozen=True)
class _RegisteredTool:
    """Where a namespaced tool lives and its server-side name."""

    session: ClientSession
    server: str
    remote_name: str
    definition: ToolDefinition


class MCPToolHub(ToolExecutor):
    """Connect to configured MCP servers and expose their tools as ``server__tool``.

    Connections are opened by :meth:`connect` and must be closed by
    :meth:`aclose` from the same task, which the application lifespan guarantees.
    A server that fails to connect is logged and skipped.
    """

    def __init__(self, configs: list[MCPServerConfig], *, timeout_seconds: float) -> None:
        self._configs = configs
        self._timeout = timedelta(seconds=timeout_seconds)
        self._stack = AsyncExitStack()
        self._tools: dict[str, _RegisteredTool] = {}
        self._logger = get_logger(__name__)

    async def connect(self) -> None:
        """Open every configured server and register its tools."""
        for config in self._configs:
            server_stack = AsyncExitStack()
            try:
                session = await self._open_session(config, server_stack)
                listing = await session.list_tools()
            except Exception as error:
                await self._close_quietly(server_stack)
                self._logger.warning(
                    "MCP server unavailable | server=%s error_type=%s error=%s",
                    config.name,
                    type(error).__name__,
                    error,
                )
                continue

            self._stack.push_async_callback(server_stack.aclose)
            for tool in listing.tools:
                name = self._namespaced(config.name, tool.name)
                self._tools[name] = _RegisteredTool(
                    session=session,
                    server=config.name,
                    remote_name=tool.name,
                    definition=ToolDefinition(
                        name=name,
                        description=tool.description or tool.title or tool.name,
                        input_schema=tool.inputSchema or {"type": "object", "properties": {}},
                    ),
                )
            self._logger.info("MCP server connected | server=%s tools=%d", config.name, len(listing.tools))

    async def aclose(self) -> None:
        """Close every server connection and stop stdio subprocesses."""
        self._tools.clear()
        await self._close_quietly(self._stack)

    def list_tools(self) -> list[ToolDefinition]:
        """Return the namespaced definitions of every connected tool."""
        return [tool.definition for tool in self._tools.values()]

    def connected_servers(self) -> list[str]:
        """Return the names of servers that contributed tools."""
        return sorted({tool.server for tool in self._tools.values()})

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a namespaced tool and normalize its result to text."""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(output=f"Unknown tool '{name}'.", is_error=True)
        try:
            result = await tool.session.call_tool(tool.remote_name, arguments)
        except Exception as error:
            self._logger.warning(
                "MCP tool call failed | server=%s tool=%s error_type=%s",
                tool.server,
                tool.remote_name,
                type(error).__name__,
            )
            return ToolResult(output=f"Tool '{name}' failed: {error}", is_error=True)
        return ToolResult(output=self._to_text(result), is_error=bool(result.isError))

    async def _open_session(self, config: MCPServerConfig, stack: AsyncExitStack) -> ClientSession:
        """Start the transport for ``config`` and return an initialized session."""
        if config.transport == "stdio":
            command = sys.executable if config.command == "python" else config.command
            parameters = StdioServerParameters(
                command=command or "",
                args=config.args,
                env=config.env or None,
                cwd=_BACKEND_DIRECTORY,
            )
            read_stream, write_stream = await stack.enter_async_context(stdio_client(parameters))
        else:
            read_stream, write_stream, _ = await stack.enter_async_context(
                streamablehttp_client(config.url or "", headers=config.headers, timeout=self._timeout)
            )
        session = await stack.enter_async_context(
            ClientSession(read_stream, write_stream, read_timeout_seconds=self._timeout)
        )
        await session.initialize()
        return session

    async def _close_quietly(self, stack: AsyncExitStack) -> None:
        """Close ``stack`` without letting transport shutdown errors escape."""
        try:
            await stack.aclose()
        except Exception as error:
            self._logger.debug("MCP connection close error | error_type=%s", type(error).__name__)

    @staticmethod
    def _namespaced(server: str, tool: str) -> str:
        """Build a model-safe tool name, unique across servers."""
        safe_tool = re.sub(r"[^A-Za-z0-9_-]", "_", tool)
        return f"{server}{_TOOL_NAME_SEPARATOR}{safe_tool}"[:_MAX_TOOL_NAME_LENGTH]

    @staticmethod
    def _to_text(result: CallToolResult) -> str:
        """Flatten MCP content blocks to text the model can read."""
        parts = [
            block.text if isinstance(block, TextContent) else f"[{block.type} content omitted]"
            for block in result.content
        ]
        if not parts and result.structuredContent is not None:
            parts.append(str(result.structuredContent))
        text = "\n".join(parts) or "(no output)"
        if len(text) > MAX_TOOL_OUTPUT_CHARS:
            return text[:MAX_TOOL_OUTPUT_CHARS] + "\n...[output truncated]"
        return text

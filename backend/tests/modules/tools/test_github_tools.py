"""Tests for the per-user GitHub tools and the composite executor, with mocked GitHub responses."""

from __future__ import annotations

import base64
import json
import unittest
from collections.abc import Callable

import httpx

from app.modules.llm.domain.models import ToolDefinition
from app.modules.tools.domain.interfaces import ToolExecutor
from app.modules.tools.domain.models import ToolResult
from app.modules.tools.infrastructure.composite import CompositeToolExecutor
from app.modules.tools.infrastructure.github_tools import GitHubToolset


class GitHubToolsetTests(unittest.IsolatedAsyncioTestCase):
    async def _call(self, handler: Callable[[httpx.Request], httpx.Response], name: str, arguments: dict[str, object]) -> ToolResult:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await GitHubToolset(http, "gho_user").call_tool(name, arguments)

    async def test_lists_issues_with_user_token_and_skips_pull_requests(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=[{"number": 1, "title": "Bug", "state": "open", "user": {"login": "a"}}, {"number": 2, "pull_request": {}}])

        result = await self._call(handler, "github__list_issues", {"owner": "octo", "repo": "app", "limit": 5})
        self.assertFalse(result.is_error)
        self.assertEqual([issue["number"] for issue in json.loads(result.output)], [1])
        self.assertEqual(seen[0].headers["authorization"], "Bearer gho_user")
        self.assertEqual(seen[0].url.path, "/repos/octo/app/issues")
        self.assertEqual(seen[0].url.params["per_page"], "5")

    async def test_reads_file_contents(self) -> None:
        encoded = base64.b64encode(b"print('hi')\n").decode()
        result = await self._call(
            lambda _: httpx.Response(200, json={"type": "file", "path": "main.py", "encoding": "base64", "content": encoded}),
            "github__get_file_contents",
            {"owner": "octo", "repo": "app", "path": "main.py"},
        )
        self.assertEqual(result.output, "main.py:\nprint('hi')\n")

    async def test_rejects_unsafe_names_without_calling_github(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            raise AssertionError("GitHub must not be called")

        for arguments in ({"owner": "../user", "repo": "x"}, {"owner": "o", "repo": "r", "path": "a/../../secrets"}):
            result = await self._call(handler, "github__get_file_contents", arguments)
            self.assertTrue(result.is_error)

    async def test_maps_http_errors_to_actionable_messages(self) -> None:
        unauthorized = await self._call(lambda _: httpx.Response(401), "github__get_me", {})
        self.assertIn("reconnect GitHub", unauthorized.output)
        missing = await self._call(lambda _: httpx.Response(404), "github__get_repository", {"owner": "o", "repo": "r"})
        self.assertTrue(missing.is_error)


class StaticTools(ToolExecutor):
    def __init__(self, name: str) -> None:
        self._name = name

    def list_tools(self) -> list[ToolDefinition]:
        return [ToolDefinition(name=self._name)]

    async def call_tool(self, name: str, arguments: dict[str, object]) -> ToolResult:
        return ToolResult(output=f"ran {name}")


class CompositeToolExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_routes_calls_to_the_owning_executor(self) -> None:
        composite = CompositeToolExecutor([StaticTools("basics__calculator"), StaticTools("github__get_me")])
        self.assertEqual([tool.name for tool in composite.list_tools()], ["basics__calculator", "github__get_me"])
        self.assertEqual((await composite.call_tool("github__get_me", {})).output, "ran github__get_me")
        self.assertTrue((await composite.call_tool("nope", {})).is_error)

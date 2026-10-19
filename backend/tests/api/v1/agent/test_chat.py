"""Endpoint tests for the agent API using fake services."""

from __future__ import annotations

import unittest
from typing import Any

from fastapi.testclient import TestClient

from app.api.v1.agent.dependencies import get_chat_agent_service, get_tool_executor
from app.main import app
from app.modules.agent.application.chat import AgentChatFailedError, ChatResult
from app.modules.llm.domain.models import ToolDefinition
from app.modules.tools.domain.models import ToolInvocation


class FakeChatService:
    """Record the command and return a controlled result."""

    def __init__(self) -> None:
        self.error: Exception | None = None
        self.command: Any = None

    async def chat(self, command: Any) -> ChatResult:
        self.command = command
        if self.error:
            raise self.error
        return ChatResult(
            content="It is 4.",
            tool_invocations=[ToolInvocation(name="basics__calculator", arguments={"expression": "2+2"}, output="2+2 = 4")],
            steps=2,
            request_id=command.request_id or "generated",
        )


class FakeTools:
    def list_tools(self) -> list[ToolDefinition]:
        return [ToolDefinition(name="basics__calculator", description="Math", input_schema={"type": "object"})]


class AgentEndpointTests(unittest.TestCase):
    """Verify controller mapping without Ollama or MCP servers."""

    def setUp(self) -> None:
        self.service = FakeChatService()
        app.dependency_overrides[get_chat_agent_service] = lambda: self.service
        app.dependency_overrides[get_tool_executor] = FakeTools
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()

    def test_chat_returns_reply_and_tool_invocations(self) -> None:
        response = self.client.post(
            "/api/v1/agent/chat",
            headers={"X-Request-ID": "req-9"},
            json={"messages": [{"role": "user", "content": "What is 2+2?"}]},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["content"], "It is 4.")
        self.assertEqual(data["tool_invocations"][0]["name"], "basics__calculator")
        self.assertEqual(self.service.command.request_id, "req-9")

    def test_rejects_tool_role_from_clients(self) -> None:
        response = self.client.post("/api/v1/agent/chat", json={"messages": [{"role": "tool", "content": "x"}]})
        self.assertEqual(response.status_code, 422)

    def test_failure_maps_to_502(self) -> None:
        self.service.error = AgentChatFailedError()
        response = self.client.post("/api/v1/agent/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"]["code"], "AGENT_CHAT_FAILED")

    def test_lists_tools(self) -> None:
        response = self.client.get("/api/v1/agent/tools")
        self.assertEqual(response.json()["data"][0]["name"], "basics__calculator")

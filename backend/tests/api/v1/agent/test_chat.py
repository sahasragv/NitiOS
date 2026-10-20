"""Endpoint tests for the agent API using fake services."""

from __future__ import annotations

import json
import unittest
from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient

from app.api.v1.agent.dependencies import get_chat_agent_service, get_model_info, get_title_service, get_tool_executor
from app.api.v1.auth.dependencies import get_auth_service, get_current_user
from app.main import app
from app.modules.accounts.domain.models import User
from app.modules.agent.application.chat import (
    AgentChatFailedError,
    ChatCompletedEvent,
    ChatEvent,
    ChatResult,
    TextDeltaEvent,
    ToolFinishedEvent,
    ToolStartedEvent,
)
from app.modules.llm.domain.models import ToolDefinition
from app.modules.tools.domain.models import ToolInvocation


class FakeChatService:
    """Record the command and return a controlled result."""

    def __init__(self) -> None:
        self.error: Exception | None = None
        self.command: Any = None

    async def chat(self, command: Any, tools: Any = None) -> ChatResult:
        self.command = command
        self.tools = tools
        if self.error:
            raise self.error
        return ChatResult(
            content="It is 4.",
            tool_invocations=[ToolInvocation(name="basics__calculator", arguments={"expression": "2+2"}, output="2+2 = 4")],
            steps=2,
            request_id=command.request_id or "generated",
        )

    async def stream_chat(self, command: Any, tools: Any = None) -> AsyncIterator[ChatEvent]:
        self.command = command
        self.tools = tools
        yield ToolStartedEvent(id="c1", name="basics__calculator", arguments={"expression": "2+2"})
        yield ToolFinishedEvent(id="c1", name="basics__calculator", output="2+2 = 4", is_error=False)
        yield TextDeltaEvent(text="It is 4.")
        if self.error:
            raise self.error
        yield ChatCompletedEvent(result=await self.chat(command))


class FakeTools:
    def list_tools(self) -> list[ToolDefinition]:
        return [ToolDefinition(name="basics__calculator", description="Math", input_schema={"type": "object"})]


class SignedOutAuth:
    async def user_for_session(self, token: str) -> None:
        return None


class FakeTitleService:
    async def suggest_title(self, message: str, reply: str | None = None) -> str:
        return f"Title for {message}"


class AgentEndpointTests(unittest.TestCase):
    """Verify controller mapping without Ollama or MCP servers."""

    def setUp(self) -> None:
        self.service = FakeChatService()
        app.dependency_overrides[get_chat_agent_service] = lambda: self.service
        app.dependency_overrides[get_tool_executor] = FakeTools
        app.dependency_overrides[get_title_service] = FakeTitleService
        app.dependency_overrides[get_model_info] = lambda: {"provider": "ollama", "model": "qwen2.5:7b"}
        app.dependency_overrides[get_current_user] = lambda: User(id="u1", email="a@example.com", name="A")
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
        self.assertIsInstance(self.service.tools, FakeTools)

    def test_requires_sign_in(self) -> None:
        del app.dependency_overrides[get_current_user]
        app.dependency_overrides[get_auth_service] = lambda: SignedOutAuth()
        response = self.client.post("/api/v1/agent/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "AUTH_REQUIRED")

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

    def _stream_events(self) -> list[dict[str, Any]]:
        response = self.client.post("/api/v1/agent/chat/stream", json={"messages": [{"role": "user", "content": "2+2?"}]})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
        return [json.loads(line.removeprefix("data: ")) for line in response.text.split("\n\n") if line.startswith("data: ")]

    def test_stream_emits_events_in_order(self) -> None:
        events = self._stream_events()
        self.assertEqual([event["type"] for event in events], ["tool_started", "tool_finished", "text_delta", "completed"])
        self.assertEqual(events[-1]["result"]["content"], "It is 4.")

    def test_stream_failure_ends_with_error_event(self) -> None:
        self.service.error = AgentChatFailedError()
        events = self._stream_events()
        self.assertEqual(events[-1], {"type": "error", "code": "AGENT_CHAT_FAILED", "message": "The assistant is currently unavailable."})

    def test_title_endpoint(self) -> None:
        response = self.client.post("/api/v1/agent/title", json={"message": "weather", "reply": "Sunny"})
        self.assertEqual(response.json()["data"], {"title": "Title for weather"})

    def test_info_endpoint(self) -> None:
        data = self.client.get("/api/v1/agent/info").json()["data"]
        self.assertEqual(data, {"provider": "ollama", "model": "qwen2.5:7b", "tool_count": 1, "servers": ["basics"]})

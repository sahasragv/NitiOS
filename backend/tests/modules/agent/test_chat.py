"""Unit tests for the agent model/tool loop using scripted fakes."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator
from typing import Any

from app.modules.agent.application.chat import (
    EMPTY_REPLY_FALLBACK,
    AgentChatFailedError,
    ChatAgentService,
    ChatCommand,
    ChatCompletedEvent,
    TextDeltaEvent,
    ToolFinishedEvent,
    ToolStartedEvent,
)
from app.modules.llm.domain.interfaces import GenerationProvider, LLMProviderInfrastructureError
from app.modules.llm.domain.models import LLMMessage, LLMRequest, LLMResponse, LLMStreamChunk, LLMUsage, ToolCall, ToolDefinition
from app.modules.llm.gateway.generation import LLMGateway
from app.modules.tools.domain.interfaces import ToolExecutor
from app.modules.tools.domain.models import ToolResult


class ScriptedProvider(GenerationProvider):
    """Return queued responses in order and record every request."""

    def __init__(self, responses: list[LLMResponse | Exception]) -> None:
        self.responses = responses
        self.requests: list[LLMRequest] = []

    @property
    def name(self) -> str:
        return "scripted"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        self.requests.append(request.model_copy(deep=True))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        for word in (response.content or "").split(" "):
            if word:
                yield LLMStreamChunk(content_delta=word + " ")
        yield LLMStreamChunk(tool_calls=response.tool_calls, finish_reason=response.finish_reason, usage=response.usage)


class FakeTools(ToolExecutor):
    """Expose one calculator tool and record calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list_tools(self) -> list[ToolDefinition]:
        return [ToolDefinition(name="basics__calculator", description="Math", input_schema={"type": "object"})]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        self.calls.append((name, arguments))
        return ToolResult(output="2 + 2 = 4")


def _response(content: str | None = None, tool_calls: list[ToolCall] | None = None) -> LLMResponse:
    return LLMResponse(
        content=content,
        tool_calls=tool_calls or [],
        provider="scripted",
        model="test",
        usage=LLMUsage(input_tokens=10, output_tokens=5, total_tokens=15),
        finish_reason="stop",
    )


class ChatAgentServiceTests(unittest.IsolatedAsyncioTestCase):
    """Verify the loop executes tools, feeds results back, and terminates."""

    def _command(self) -> ChatCommand:
        return ChatCommand(messages=[LLMMessage(role="user", content="What is 2 + 2?")], request_id="req-1")

    async def test_answers_directly_without_tools(self) -> None:
        provider, tools = ScriptedProvider([_response("Hello!")]), FakeTools()
        result = await ChatAgentService(LLMGateway(provider), tools, max_steps=4).chat(self._command())

        self.assertEqual(result.content, "Hello! ")
        self.assertEqual(result.steps, 1)
        self.assertEqual(tools.calls, [])
        self.assertEqual(provider.requests[0].messages[0].role, "system")
        self.assertEqual([tool.name for tool in provider.requests[0].tools], ["basics__calculator"])

    async def test_executes_tool_and_feeds_result_back(self) -> None:
        call = ToolCall(id="call-1", name="basics__calculator", arguments={"expression": "2 + 2"})
        provider, tools = ScriptedProvider([_response(tool_calls=[call]), _response("It is 4.")]), FakeTools()
        result = await ChatAgentService(LLMGateway(provider), tools, max_steps=4).chat(self._command())

        self.assertEqual(result.content, "It is 4. ")
        self.assertEqual(result.steps, 2)
        self.assertEqual(tools.calls, [("basics__calculator", {"expression": "2 + 2"})])
        self.assertEqual(result.tool_invocations[0].output, "2 + 2 = 4")
        self.assertEqual(result.usage.total_tokens, 30)
        follow_up = provider.requests[1].messages
        self.assertEqual(follow_up[-2].tool_calls, [call])
        self.assertEqual((follow_up[-1].role, follow_up[-1].content, follow_up[-1].tool_call_id), ("tool", "2 + 2 = 4", "call-1"))

    async def test_final_step_withholds_tools_to_force_an_answer(self) -> None:
        call = ToolCall(id="call-1", name="basics__calculator", arguments={})
        provider = ScriptedProvider([_response(tool_calls=[call]), _response("Done.")])
        result = await ChatAgentService(LLMGateway(provider), FakeTools(), max_steps=2).chat(self._command())

        self.assertEqual(result.content, "Done. ")
        self.assertEqual(provider.requests[1].tools, [])

    async def test_provider_failure_maps_to_application_error(self) -> None:
        provider = ScriptedProvider([LLMProviderInfrastructureError("down")])
        with self.assertRaises(AgentChatFailedError):
            await ChatAgentService(LLMGateway(provider), FakeTools(), max_steps=4).chat(self._command())

    async def test_stream_emits_tool_events_between_text(self) -> None:
        call = ToolCall(id="call-1", name="basics__calculator", arguments={"expression": "2 + 2"})
        provider = ScriptedProvider([_response("Let me check.", tool_calls=[call]), _response("It is 4.")])
        service = ChatAgentService(LLMGateway(provider), FakeTools(), max_steps=4)
        events = [event async for event in service.stream_chat(self._command())]

        self.assertEqual([type(event) for event in events], [
            TextDeltaEvent, TextDeltaEvent, TextDeltaEvent, ToolStartedEvent, ToolFinishedEvent, TextDeltaEvent, TextDeltaEvent, TextDeltaEvent, ChatCompletedEvent,
        ])
        started, finished = events[3], events[4]
        assert isinstance(started, ToolStartedEvent) and isinstance(finished, ToolFinishedEvent)
        self.assertEqual((started.id, finished.id, finished.output), ("call-1", "call-1", "2 + 2 = 4"))
        completed = events[-1]
        assert isinstance(completed, ChatCompletedEvent)
        self.assertEqual(completed.result.content, "It is 4. ")

    async def test_empty_step_is_retried_without_tools(self) -> None:
        provider = ScriptedProvider([_response(""), _response("Here is the answer.")])
        result = await ChatAgentService(LLMGateway(provider), FakeTools(), max_steps=4).chat(self._command())

        self.assertEqual(result.content, "Here is the answer. ")
        self.assertEqual(len(provider.requests[0].tools), 1)
        self.assertEqual(provider.requests[1].tools, [])

    async def test_repeated_empty_reply_returns_fallback_text(self) -> None:
        provider = ScriptedProvider([_response(""), _response("")])
        result = await ChatAgentService(LLMGateway(provider), FakeTools(), max_steps=4).chat(self._command())
        self.assertEqual(result.content, EMPTY_REPLY_FALLBACK)


class AgentChatFailedErrorTests(unittest.TestCase):
    """Verify provider failures map to helpful, safe messages."""

    def test_messages_explain_common_causes(self) -> None:
        from app.modules.llm.providers.ollama.client import OllamaProviderError

        cases = {
            OllamaProviderError("x", reason="ReadTimeout"): "took too long",
            OllamaProviderError("x", reason="ConnectError"): "Make sure Ollama is running",
            OllamaProviderError("x", status_code=404, reason="http_status_error"): "model isn’t available",
            OllamaProviderError("x", reason="something_else"): "currently unavailable",
        }
        for error, expected in cases.items():
            with self.subTest(reason=error.reason):
                self.assertIn(expected, AgentChatFailedError.from_provider_error(error).message)

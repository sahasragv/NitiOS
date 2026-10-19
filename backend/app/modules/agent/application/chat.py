"""Application service for a tool-using chat turn."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.exceptions.base import BaseApplicationException
from app.modules.llm.domain.interfaces import LLMProviderInfrastructureError
from app.modules.llm.domain.models import LLMCapability, LLMMessage, LLMRequest, LLMUsage, RequestMetadata, ToolCall
from app.modules.llm.gateway.generation import LLMGateway, LLMGatewayRequestError
from app.modules.tools.domain.interfaces import ToolExecutor
from app.modules.tools.domain.models import ToolInvocation


DEFAULT_SYSTEM_PROMPT = (
    "You are Setu, a helpful assistant with access to tools. "
    "Use a tool whenever it gives a more accurate answer than you can on your own: "
    "arithmetic, unit and currency conversion, the current time or time-zone conversion, weather, translation, "
    "and connected apps such as GitHub. Prefer a dedicated conversion tool over writing a formula for the calculator. "
    "Never invent tool results. If a tool returns an error you can fix, such as a wrong argument format, "
    "call it again with corrected arguments instead of asking the user. "
    "If it still fails, say so briefly and suggest what the user can do. "
    "Language: always reply in the language the user asks for, or else the language they write in. "
    "This includes Indian languages such as Telugu, Hindi, Tamil, Kannada, Malayalam, Marathi, Bengali, Gujarati, "
    "Punjabi and Urdu, written in their native script. Write such answers yourself; use the translate tool only "
    "when the user asks to translate a specific piece of text. "
    "Answer concisely and use Markdown where it helps readability. The current UTC time is {now}."
)
EMPTY_REPLY_FALLBACK = "I couldn't produce an answer this time. Please try again or rephrase your question."


class ChatCommand(BaseModel):
    """Application input for one chat turn, including prior conversation history."""

    messages: list[LLMMessage] = Field(min_length=1)
    request_id: str | None = None


class ChatResult(BaseModel):
    """Final assistant reply plus the tools used to produce it."""

    content: str | None = None
    tool_invocations: list[ToolInvocation] = Field(default_factory=list)
    finish_reason: str | None = None
    usage: LLMUsage = Field(default_factory=LLMUsage)
    steps: int
    request_id: str


class TextDeltaEvent(BaseModel):
    """A fragment of assistant text, emitted as the model generates it."""

    type: Literal["text_delta"] = "text_delta"
    text: str


class ToolStartedEvent(BaseModel):
    """The model requested a tool and execution has begun."""

    type: Literal["tool_started"] = "tool_started"
    id: str
    name: str
    arguments: dict[str, Any]


class ToolFinishedEvent(BaseModel):
    """A tool finished; ``id`` matches the corresponding started event."""

    type: Literal["tool_finished"] = "tool_finished"
    id: str
    name: str
    output: str
    is_error: bool


class ChatCompletedEvent(BaseModel):
    """The turn is complete; always the last event of a successful stream."""

    type: Literal["completed"] = "completed"
    result: ChatResult


ChatEvent = TextDeltaEvent | ToolStartedEvent | ToolFinishedEvent | ChatCompletedEvent


class AgentChatRequestError(BaseApplicationException):
    """Expected failure caused by an invalid chat input."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="AGENT_CHAT_REQUEST_INVALID", status_code=422)


class AgentChatFailedError(BaseApplicationException):
    """Expected failure when the language model is unreachable during a chat turn."""

    def __init__(self, message: str = "The assistant is currently unavailable.") -> None:
        super().__init__(message, error_code="AGENT_CHAT_FAILED", status_code=502)

    @classmethod
    def from_provider_error(cls, error: LLMProviderInfrastructureError) -> "AgentChatFailedError":
        """Explain the likely cause using the provider's failure reason, without leaking details."""
        reason = str(getattr(error, "reason", "") or "")
        status = getattr(error, "status_code", None)
        if "Timeout" in reason:
            return cls("The model took too long to respond. Local models on a CPU can be slow — try again or use a shorter question.")
        if reason in {"ConnectError", "ConnectTimeout"}:
            return cls("Can’t reach the model server. Make sure Ollama is running.")
        if status == 404:
            return cls("The configured model isn’t available. Check the model name in backend/.env.")
        if reason == "authentication_error" or status == 401:
            return cls("The model provider rejected the API key. Check it in backend/.env.")
        return cls()


class ChatAgentService:
    """Run the model/tool loop until the model answers or ``max_steps`` is reached."""

    def __init__(
        self,
        gateway: LLMGateway,
        tools: ToolExecutor,
        *,
        max_steps: int,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        self._gateway = gateway
        self._tools = tools
        self._max_steps = max_steps
        self._system_prompt = system_prompt
        self._logger = get_logger(__name__)

    async def chat(self, command: ChatCommand) -> ChatResult:
        """Answer the latest user message and return only the final result."""
        async for event in self.stream_chat(command):
            if isinstance(event, ChatCompletedEvent):
                return event.result
        raise AgentChatFailedError()

    async def stream_chat(self, command: ChatCommand) -> AsyncIterator[ChatEvent]:
        """Answer the latest user message, yielding text and tool events as they happen."""
        request_id = command.request_id or str(uuid4())
        started_at = perf_counter()
        system_message = LLMMessage(
            role="system",
            content=self._system_prompt.format(now=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")),
        )
        conversation = [system_message, *command.messages]
        invocations: list[ToolInvocation] = []
        usage = LLMUsage()
        tools = self._tools.list_tools()
        # Set when a step returns neither text nor tool calls; the next step must answer in plain text.
        withhold_tools = False

        try:
            for step in range(1, self._max_steps + 1):
                content_parts: list[str] = []
                tool_calls: list[ToolCall] = []
                finish_reason: str | None = None
                # The last step withholds tools so the model must answer from what it has.
                request = LLMRequest(
                    capability=LLMCapability.REASONING,
                    messages=conversation,
                    tools=tools if step < self._max_steps and not withhold_tools else [],
                    metadata=RequestMetadata(request_id=request_id),
                )
                async for chunk in self._gateway.stream(request):
                    if chunk.content_delta:
                        content_parts.append(chunk.content_delta)
                        yield TextDeltaEvent(text=chunk.content_delta)
                    tool_calls.extend(chunk.tool_calls)
                    if chunk.usage:
                        usage = self._add_usage(usage, chunk.usage)
                    finish_reason = chunk.finish_reason or finish_reason

                content = "".join(content_parts)
                if not tool_calls and not content.strip() and not withhold_tools and step < self._max_steps:
                    # Small models occasionally emit an unparseable tool call; retry once without tools.
                    withhold_tools = True
                    continue
                if not tool_calls:
                    self._log_outcome(request_id, step, len(invocations), started_at, success=True)
                    yield ChatCompletedEvent(
                        result=ChatResult(
                            content=content if content.strip() else EMPTY_REPLY_FALLBACK,
                            tool_invocations=invocations,
                            finish_reason=finish_reason,
                            usage=usage,
                            steps=step,
                            request_id=request_id,
                        )
                    )
                    return

                conversation.append(LLMMessage(role="assistant", content=content, tool_calls=tool_calls))
                for call in tool_calls:
                    call_id = call.id or f"call_{uuid4().hex[:12]}"
                    yield ToolStartedEvent(id=call_id, name=call.name, arguments=call.arguments)
                    result = await self._tools.call_tool(call.name, call.arguments)
                    invocations.append(
                        ToolInvocation(
                            name=call.name,
                            arguments=call.arguments,
                            output=result.output,
                            is_error=result.is_error,
                        )
                    )
                    yield ToolFinishedEvent(id=call_id, name=call.name, output=result.output, is_error=result.is_error)
                    conversation.append(
                        LLMMessage(role="tool", content=result.output, name=call.name, tool_call_id=call_id)
                    )
        except LLMGatewayRequestError as error:
            self._log_outcome(request_id, 0, len(invocations), started_at, success=False)
            raise AgentChatRequestError(str(error)) from error
        except LLMProviderInfrastructureError as error:
            self._log_outcome(request_id, 0, len(invocations), started_at, success=False)
            raise AgentChatFailedError.from_provider_error(error) from error

        self._log_outcome(request_id, self._max_steps, len(invocations), started_at, success=True)
        yield ChatCompletedEvent(
            result=ChatResult(
                content="I couldn't finish this request within the allowed number of steps.",
                tool_invocations=invocations,
                finish_reason="max_steps",
                usage=usage,
                steps=self._max_steps,
                request_id=request_id,
            )
        )

    @staticmethod
    def _add_usage(total: LLMUsage, addition: LLMUsage) -> LLMUsage:
        """Accumulate token usage across the model calls of one turn."""
        return LLMUsage(
            input_tokens=total.input_tokens + addition.input_tokens,
            output_tokens=total.output_tokens + addition.output_tokens,
            total_tokens=total.total_tokens + addition.total_tokens,
        )

    def _log_outcome(self, request_id: str, steps: int, tool_calls: int, started_at: float, *, success: bool) -> None:
        """Log safe telemetry without message content or tool arguments."""
        (self._logger.info if success else self._logger.error)(
            "Agent chat completed" if success else "Agent chat failed",
            extra={
                "request_id": request_id,
                "steps": steps,
                "tool_calls": tool_calls,
                "latency_ms": round((perf_counter() - started_at) * 1000, 2),
                "success": success,
            },
        )

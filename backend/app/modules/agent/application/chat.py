"""Application service for a tool-using chat turn."""

from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.exceptions.base import BaseApplicationException
from app.modules.llm.domain.interfaces import LLMProviderInfrastructureError
from app.modules.llm.domain.models import LLMCapability, LLMMessage, LLMRequest, LLMUsage, RequestMetadata
from app.modules.llm.gateway.generation import LLMGateway, LLMGatewayRequestError
from app.modules.tools.domain.interfaces import ToolExecutor
from app.modules.tools.domain.models import ToolInvocation


DEFAULT_SYSTEM_PROMPT = (
    "You are Setu, a helpful assistant with access to tools. "
    "Use a tool whenever it gives a more accurate answer than you can on your own: "
    "arithmetic, the current time or time-zone conversion, weather, translation, and connected apps such as GitHub. "
    "Never invent tool results. If a tool returns an error you can fix, such as a wrong argument format, "
    "call it again with corrected arguments instead of asking the user. "
    "If it still fails, say so briefly and suggest what the user can do. "
    "Answer concisely. The current UTC time is {now}."
)


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


class AgentChatRequestError(BaseApplicationException):
    """Expected failure caused by an invalid chat input."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="AGENT_CHAT_REQUEST_INVALID", status_code=422)


class AgentChatFailedError(BaseApplicationException):
    """Expected failure when the language model is unreachable during a chat turn."""

    def __init__(self) -> None:
        super().__init__("The assistant is currently unavailable.", error_code="AGENT_CHAT_FAILED", status_code=502)


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
        """Answer the latest user message, calling tools as the model requests them."""
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

        try:
            for step in range(1, self._max_steps + 1):
                # The last step withholds tools so the model must answer from what it has.
                response = await self._gateway.generate(
                    LLMRequest(
                        capability=LLMCapability.REASONING,
                        messages=conversation,
                        tools=tools if step < self._max_steps else [],
                        metadata=RequestMetadata(request_id=request_id),
                    )
                )
                usage = self._add_usage(usage, response.usage)
                if not response.tool_calls:
                    self._log_outcome(request_id, step, len(invocations), started_at, success=True)
                    return ChatResult(
                        content=response.content,
                        tool_invocations=invocations,
                        finish_reason=response.finish_reason,
                        usage=usage,
                        steps=step,
                        request_id=request_id,
                    )

                conversation.append(
                    LLMMessage(role="assistant", content=response.content or "", tool_calls=response.tool_calls)
                )
                for call in response.tool_calls:
                    result = await self._tools.call_tool(call.name, call.arguments)
                    invocations.append(
                        ToolInvocation(
                            name=call.name,
                            arguments=call.arguments,
                            output=result.output,
                            is_error=result.is_error,
                        )
                    )
                    conversation.append(
                        LLMMessage(role="tool", content=result.output, name=call.name, tool_call_id=call.id)
                    )
        except LLMGatewayRequestError as error:
            self._log_outcome(request_id, 0, len(invocations), started_at, success=False)
            raise AgentChatRequestError(str(error)) from error
        except LLMProviderInfrastructureError as error:
            self._log_outcome(request_id, 0, len(invocations), started_at, success=False)
            raise AgentChatFailedError() from error

        self._log_outcome(request_id, self._max_steps, len(invocations), started_at, success=True)
        return ChatResult(
            content="I couldn't finish this request within the allowed number of steps.",
            tool_invocations=invocations,
            finish_reason="max_steps",
            usage=usage,
            steps=self._max_steps,
            request_id=request_id,
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

"""Thin HTTP controller for the tool-using chat agent."""

from collections.abc import AsyncIterator
from typing import Literal

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.v1.agent.dependencies import get_chat_agent_service, get_model_info, get_title_service, get_tool_executor
from app.api.v1.agent.schemas import (
    AgentInfoDTO,
    ChatRequestDTO,
    ChatResponseDTO,
    ChatUsageDTO,
    TitleRequestDTO,
    TitleResponseDTO,
    ToolDTO,
    ToolInvocationDTO,
)
from app.common.responses import ResponseMeta, SuccessResponse
from app.core.logging import get_logger
from app.exceptions.base import BaseApplicationException
from app.modules.agent.application.chat import ChatAgentService, ChatCommand
from app.modules.agent.application.title import ConversationTitleService
from app.modules.llm.domain.models import LLMMessage
from app.modules.tools.domain.interfaces import ToolExecutor


router = APIRouter(prefix="/api/v1/agent", tags=["agent"])
_logger = get_logger(__name__)


class ChatErrorEvent(BaseModel):
    """Terminal stream event sent when a turn fails after streaming has begun."""

    type: Literal["error"] = "error"
    code: str
    message: str


def _to_command(body: ChatRequestDTO, request_id: str | None) -> ChatCommand:
    """Map the HTTP request body to the application command."""
    return ChatCommand(
        messages=[LLMMessage(role=message.role, content=message.content) for message in body.messages],
        request_id=request_id,
    )


def _sse(event: BaseModel) -> str:
    """Encode one event as a Server-Sent Events frame."""
    return f"data: {event.model_dump_json()}\n\n"


@router.post("/chat", response_model=SuccessResponse[ChatResponseDTO])
async def chat(
    body: ChatRequestDTO,
    service: ChatAgentService = Depends(get_chat_agent_service),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> SuccessResponse[ChatResponseDTO]:
    """Delegate one chat turn to the agent application service."""
    result = await service.chat(_to_command(body, request_id))
    return SuccessResponse(
        message="Chat turn completed.",
        data=ChatResponseDTO(
            content=result.content,
            tool_invocations=[ToolInvocationDTO(**invocation.model_dump()) for invocation in result.tool_invocations],
            finish_reason=result.finish_reason,
            usage=ChatUsageDTO(**result.usage.model_dump()),
            steps=result.steps,
            request_id=result.request_id,
        ),
        meta=ResponseMeta(request_id=result.request_id, version="v1"),
    )


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequestDTO,
    service: ChatAgentService = Depends(get_chat_agent_service),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> StreamingResponse:
    """Stream one chat turn as Server-Sent Events.

    Each ``data:`` frame is a JSON object whose ``type`` is ``text_delta``,
    ``tool_started``, ``tool_finished``, ``completed`` (always last on success)
    or ``error`` (last on failure).
    """
    command = _to_command(body, request_id)

    async def events() -> AsyncIterator[str]:
        try:
            async for event in service.stream_chat(command):
                yield _sse(event)
        except BaseApplicationException as error:
            yield _sse(ChatErrorEvent(code=error.error_code, message=error.message))
        except Exception:
            _logger.exception("Unhandled error while streaming a chat turn.")
            yield _sse(ChatErrorEvent(code="INTERNAL_SERVER_ERROR", message="An unexpected error occurred."))

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/tools", response_model=SuccessResponse[list[ToolDTO]])
async def list_tools(tools: ToolExecutor = Depends(get_tool_executor)) -> SuccessResponse[list[ToolDTO]]:
    """List every tool the assistant can currently use."""
    return SuccessResponse(
        message="Available tools.",
        data=[ToolDTO(**definition.model_dump()) for definition in tools.list_tools()],
        meta=ResponseMeta(version="v1"),
    )


@router.post("/title", response_model=SuccessResponse[TitleResponseDTO])
async def suggest_title(
    body: TitleRequestDTO,
    service: ConversationTitleService = Depends(get_title_service),
) -> SuccessResponse[TitleResponseDTO]:
    """Summarize a conversation's opening exchange into a short title."""
    title = await service.suggest_title(body.message, body.reply)
    return SuccessResponse(message="Title generated.", data=TitleResponseDTO(title=title), meta=ResponseMeta(version="v1"))


@router.get("/info", response_model=SuccessResponse[AgentInfoDTO])
async def get_info(
    tools: ToolExecutor = Depends(get_tool_executor),
    model_info: dict[str, str] = Depends(get_model_info),
) -> SuccessResponse[AgentInfoDTO]:
    """Describe the active model and connected tool servers."""
    definitions = tools.list_tools()
    servers = sorted({definition.name.split("__", 1)[0] for definition in definitions if "__" in definition.name})
    return SuccessResponse(
        message="Agent info.",
        data=AgentInfoDTO(provider=model_info["provider"], model=model_info["model"], tool_count=len(definitions), servers=servers),
        meta=ResponseMeta(version="v1"),
    )

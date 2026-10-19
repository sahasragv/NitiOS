"""Thin HTTP controller for the tool-using chat agent."""

from fastapi import APIRouter, Depends, Header

from app.api.v1.agent.dependencies import get_chat_agent_service, get_tool_executor
from app.api.v1.agent.schemas import ChatRequestDTO, ChatResponseDTO, ChatUsageDTO, ToolDTO, ToolInvocationDTO
from app.common.responses import ResponseMeta, SuccessResponse
from app.modules.agent.application.chat import ChatAgentService, ChatCommand
from app.modules.llm.domain.models import LLMMessage
from app.modules.tools.domain.interfaces import ToolExecutor


router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


@router.post("/chat", response_model=SuccessResponse[ChatResponseDTO])
async def chat(
    body: ChatRequestDTO,
    service: ChatAgentService = Depends(get_chat_agent_service),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> SuccessResponse[ChatResponseDTO]:
    """Delegate one chat turn to the agent application service."""
    result = await service.chat(
        ChatCommand(
            messages=[LLMMessage(role=message.role, content=message.content) for message in body.messages],
            request_id=request_id,
        )
    )
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


@router.get("/tools", response_model=SuccessResponse[list[ToolDTO]])
async def list_tools(tools: ToolExecutor = Depends(get_tool_executor)) -> SuccessResponse[list[ToolDTO]]:
    """List every tool the assistant can currently use."""
    return SuccessResponse(
        message="Available tools.",
        data=[ToolDTO(**definition.model_dump()) for definition in tools.list_tools()],
        meta=ResponseMeta(version="v1"),
    )

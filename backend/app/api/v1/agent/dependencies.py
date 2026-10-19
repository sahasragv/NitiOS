"""FastAPI dependencies for agent application services."""

from fastapi import Request

from app.modules.agent.application.chat import ChatAgentService
from app.modules.agent.application.title import ConversationTitleService
from app.modules.tools.domain.interfaces import ToolExecutor


def get_chat_agent_service(request: Request) -> ChatAgentService:
    """Resolve the lifespan-managed chat agent from application state."""
    return request.app.state.chat_agent_service


def get_tool_executor(request: Request) -> ToolExecutor:
    """Resolve the lifespan-managed tool executor from application state."""
    return request.app.state.tool_executor


def get_title_service(request: Request) -> ConversationTitleService:
    """Resolve the lifespan-managed title service from application state."""
    return request.app.state.title_service


def get_model_info(request: Request) -> dict[str, str]:
    """Resolve the active provider and model name recorded at startup."""
    return request.app.state.model_info

"""FastAPI dependencies for agent application services."""

from fastapi import Request

from app.modules.agent.application.chat import ChatAgentService
from app.modules.tools.domain.interfaces import ToolExecutor


def get_chat_agent_service(request: Request) -> ChatAgentService:
    """Resolve the lifespan-managed chat agent from application state."""
    return request.app.state.chat_agent_service


def get_tool_executor(request: Request) -> ToolExecutor:
    """Resolve the lifespan-managed tool executor from application state."""
    return request.app.state.tool_executor

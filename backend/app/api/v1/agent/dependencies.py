"""FastAPI dependencies for agent application services."""

from fastapi import Depends, Request

from app.api.v1.auth.dependencies import get_connection_service, get_current_user
from app.modules.accounts.application.connections import ConnectionService
from app.modules.accounts.domain.models import User
from app.modules.agent.application.chat import ChatAgentService
from app.modules.agent.application.title import ConversationTitleService
from app.modules.tools.domain.interfaces import ToolExecutor
from app.modules.tools.infrastructure.composite import CompositeToolExecutor
from app.modules.tools.infrastructure.github_tools import GitHubToolset


def get_chat_agent_service(request: Request) -> ChatAgentService:
    """Resolve the lifespan-managed chat agent from application state."""
    return request.app.state.chat_agent_service


async def get_tool_executor(
    request: Request,
    user: User = Depends(get_current_user),
    connections: ConnectionService = Depends(get_connection_service),
) -> ToolExecutor:
    """Return the shared tools plus the tools of accounts the signed-in user has connected."""
    shared: ToolExecutor = request.app.state.tool_executor
    github_token = await connections.github_token(user.id)
    if not github_token:
        return shared
    return CompositeToolExecutor([shared, GitHubToolset(request.app.state.integration_http_client, github_token)])


def get_title_service(request: Request) -> ConversationTitleService:
    """Resolve the lifespan-managed title service from application state."""
    return request.app.state.title_service


def get_model_info(request: Request) -> dict[str, str]:
    """Resolve the active provider and model name recorded at startup."""
    return request.app.state.model_info

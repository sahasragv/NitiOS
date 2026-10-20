"""FastAPI dependencies for sign-in sessions and connected accounts."""

from fastapi import Cookie, Depends, Request

from app.modules.accounts.application.auth import AuthService
from app.modules.accounts.application.connections import ConnectionService
from app.modules.accounts.domain.models import AuthenticationRequiredError, User


SESSION_COOKIE = "setu_session"


def get_auth_service(request: Request) -> AuthService:
    """Resolve the lifespan-managed auth service from application state."""
    return request.app.state.auth_service


def get_connection_service(request: Request) -> ConnectionService:
    """Resolve the lifespan-managed connection service from application state."""
    return request.app.state.connection_service


async def get_current_user(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    auth: AuthService = Depends(get_auth_service),
) -> User:
    """Return the signed-in user, or fail with 401 ``AUTH_REQUIRED``."""
    user = await auth.user_for_session(session_token) if session_token else None
    if user is None:
        raise AuthenticationRequiredError()
    return user

"""Thin HTTP controllers for Google sign-in and GitHub account connection.

Both flows are browser redirects: ``/login`` sends the browser to the provider with a
random ``state`` kept in a short-lived cookie, and ``/callback`` checks that state,
finishes the exchange, and redirects back into the app with ``?auth_error=`` or
``?connection_error=`` on failure.
"""

import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Depends, Response
from fastapi.responses import RedirectResponse

from app.api.v1.auth.dependencies import SESSION_COOKIE, get_auth_service, get_connection_service, get_current_user
from app.api.v1.auth.schemas import AuthConfigDTO, ConnectionDTO, UserDTO
from app.common.responses import ResponseMeta, SuccessResponse
from app.core.settings import settings
from app.modules.accounts.application.auth import AuthService
from app.modules.accounts.application.connections import ConnectionService
from app.modules.accounts.domain.models import OAuthFlowError, User


router = APIRouter(prefix="/api/v1", tags=["auth"])

_STATE_MAX_AGE = 600
_GOOGLE_STATE_COOKIE = "setu_google_state"
_GITHUB_STATE_COOKIE = "setu_github_state"
_GOOGLE_CALLBACK = "/api/v1/auth/google/callback"
_GITHUB_CALLBACK = "/api/v1/connections/github/callback"


def _public_url(path: str = "/", **query: str) -> str:
    base = settings.PUBLIC_URL.rstrip("/") + path
    return f"{base}?{urlencode(query)}" if query else base


def _secure_cookies() -> bool:
    return settings.PUBLIC_URL.startswith("https://")


def _redirect_with_state(url_for_state: str, state: str, cookie: str, path: str) -> RedirectResponse:
    response = RedirectResponse(url_for_state, status_code=302)
    response.set_cookie(cookie, state, max_age=_STATE_MAX_AGE, path=path, httponly=True, samesite="lax", secure=_secure_cookies())
    return response


def _state_matches(expected: str | None, received: str | None) -> bool:
    return bool(expected and received and secrets.compare_digest(expected, received))


@router.get("/auth/config", response_model=SuccessResponse[AuthConfigDTO])
async def get_auth_config(
    auth: AuthService = Depends(get_auth_service),
    connections: ConnectionService = Depends(get_connection_service),
) -> SuccessResponse[AuthConfigDTO]:
    """Report which providers are configured, so the UI can explain missing setup."""
    return SuccessResponse(
        message="Auth configuration.",
        data=AuthConfigDTO(google_enabled=auth.google_enabled, github_enabled=connections.github_enabled),
        meta=ResponseMeta(version="v1"),
    )


@router.get("/auth/google/login")
async def google_login(auth: AuthService = Depends(get_auth_service)) -> RedirectResponse:
    """Start "Sign in with Google"."""
    if not auth.google_enabled:
        return RedirectResponse(_public_url(auth_error="google_not_configured"), status_code=302)
    state = secrets.token_urlsafe(24)
    url = auth.google_authorization_url(state=state, redirect_uri=_public_url(_GOOGLE_CALLBACK))
    return _redirect_with_state(url, state, _GOOGLE_STATE_COOKIE, "/api/v1/auth")


@router.get("/auth/google/callback")
async def google_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    expected_state: str | None = Cookie(default=None, alias=_GOOGLE_STATE_COOKIE),
    auth: AuthService = Depends(get_auth_service),
) -> RedirectResponse:
    """Finish Google sign-in, set the session cookie and return to the app."""
    if error or not code:
        response = RedirectResponse(_public_url(auth_error="google_cancelled" if error == "access_denied" else "google_failed"), status_code=302)
    elif not _state_matches(expected_state, state):
        response = RedirectResponse(_public_url(auth_error="state_mismatch"), status_code=302)
    else:
        try:
            _, token = await auth.sign_in_with_google(code=code, redirect_uri=_public_url(_GOOGLE_CALLBACK))
        except OAuthFlowError as flow_error:
            response = RedirectResponse(_public_url(auth_error=flow_error.reason), status_code=302)
        else:
            response = RedirectResponse(_public_url(), status_code=302)
            response.set_cookie(
                SESSION_COOKIE,
                token,
                max_age=settings.SESSION_TTL_DAYS * 86400,
                path="/",
                httponly=True,
                samesite="lax",
                secure=_secure_cookies(),
            )
    response.delete_cookie(_GOOGLE_STATE_COOKIE, path="/api/v1/auth")
    return response


@router.get("/auth/me", response_model=SuccessResponse[UserDTO])
async def get_me(user: User = Depends(get_current_user)) -> SuccessResponse[UserDTO]:
    """Return the signed-in user."""
    return SuccessResponse(message="Signed in.", data=UserDTO(**user.model_dump()), meta=ResponseMeta(version="v1"))


@router.post("/auth/logout", response_model=SuccessResponse[None])
async def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    auth: AuthService = Depends(get_auth_service),
) -> SuccessResponse[None]:
    """End the current session."""
    if session_token:
        await auth.sign_out(session_token)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return SuccessResponse(message="Signed out.", data=None, meta=ResponseMeta(version="v1"))


@router.get("/connections", response_model=SuccessResponse[list[ConnectionDTO]])
async def list_connections(
    user: User = Depends(get_current_user),
    connections: ConnectionService = Depends(get_connection_service),
) -> SuccessResponse[list[ConnectionDTO]]:
    """List the providers the user can link and which are linked."""
    linked = {connection.provider: connection for connection in await connections.list_connections(user.id)}
    github = linked.get("github")
    data = [
        ConnectionDTO(
            provider="github",
            enabled=connections.github_enabled,
            connected=github is not None,
            account=github.account if github else None,
            connected_at=github.connected_at if github else None,
        )
    ]
    return SuccessResponse(message="Connections.", data=data, meta=ResponseMeta(version="v1"))


@router.get("/connections/github/login")
async def github_login(
    _: User = Depends(get_current_user),
    connections: ConnectionService = Depends(get_connection_service),
) -> RedirectResponse:
    """Start linking the user's GitHub account."""
    if not connections.github_enabled:
        return RedirectResponse(_public_url(connection_error="github_not_configured"), status_code=302)
    state = secrets.token_urlsafe(24)
    url = connections.github_authorization_url(state=state, redirect_uri=_public_url(_GITHUB_CALLBACK))
    return _redirect_with_state(url, state, _GITHUB_STATE_COOKIE, "/api/v1/connections")


@router.get("/connections/github/callback")
async def github_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    expected_state: str | None = Cookie(default=None, alias=_GITHUB_STATE_COOKIE),
    user: User = Depends(get_current_user),
    connections: ConnectionService = Depends(get_connection_service),
) -> RedirectResponse:
    """Finish linking GitHub and return to the app."""
    if error or not code:
        target = _public_url(connection_error="github_cancelled" if error == "access_denied" else "github_failed")
    elif not _state_matches(expected_state, state):
        target = _public_url(connection_error="state_mismatch")
    else:
        try:
            await connections.connect_github(user.id, code=code, redirect_uri=_public_url(_GITHUB_CALLBACK))
            target = _public_url(connected="github")
        except OAuthFlowError as flow_error:
            target = _public_url(connection_error=flow_error.reason)
    response = RedirectResponse(target, status_code=302)
    response.delete_cookie(_GITHUB_STATE_COOKIE, path="/api/v1/connections")
    return response


@router.delete("/connections/github", response_model=SuccessResponse[None])
async def disconnect_github(
    user: User = Depends(get_current_user),
    connections: ConnectionService = Depends(get_connection_service),
) -> SuccessResponse[None]:
    """Unlink the user's GitHub account and revoke Setu's access to it."""
    await connections.disconnect_github(user.id)
    return SuccessResponse(message="GitHub disconnected.", data=None, meta=ResponseMeta(version="v1"))

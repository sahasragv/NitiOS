"""Account contracts shared by the application and HTTP layers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.exceptions.base import BaseApplicationException


ConnectionProvider = Literal["github"]


class User(BaseModel):
    """A signed-in Setu user."""

    model_config = ConfigDict(extra="forbid")

    id: str
    email: str
    name: str
    picture: str | None = None


class Connection(BaseModel):
    """A third-party account a user has linked; the token itself never leaves the server."""

    model_config = ConfigDict(extra="forbid")

    provider: ConnectionProvider
    account: str
    scopes: list[str]
    connected_at: int


class AuthenticationRequiredError(BaseApplicationException):
    """The request has no valid sign-in session."""

    def __init__(self) -> None:
        super().__init__("Please sign in to continue.", error_code="AUTH_REQUIRED", status_code=401)


class OAuthFlowError(Exception):
    """An OAuth sign-in or connection attempt failed; ``reason`` is a short, safe code for the UI."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason

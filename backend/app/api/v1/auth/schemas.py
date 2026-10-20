"""HTTP-specific DTOs for sign-in and connected accounts."""

from __future__ import annotations

from pydantic import BaseModel


class UserDTO(BaseModel):
    """The signed-in user."""

    id: str
    email: str
    name: str
    picture: str | None = None


class AuthConfigDTO(BaseModel):
    """Which sign-in and connection providers the server has credentials for."""

    google_enabled: bool
    github_enabled: bool


class ConnectionDTO(BaseModel):
    """A provider the user can link, and the linked account if any."""

    provider: str
    enabled: bool
    connected: bool
    account: str | None = None
    connected_at: int | None = None

"""HTTP clients for the Google sign-in and GitHub connection OAuth flows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from app.modules.accounts.domain.models import OAuthFlowError


GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_URL = "https://api.github.com"


@dataclass(frozen=True)
class GoogleProfile:
    """The identity fields Setu keeps from Google."""

    sub: str
    email: str
    email_verified: bool
    name: str
    picture: str | None


@dataclass(frozen=True)
class GitHubGrant:
    """A GitHub user token and the account it belongs to."""

    access_token: str
    scopes: list[str]
    login: str


class GoogleOAuthClient:
    """Authorization-code flow for "Sign in with Google" (``openid email profile`` only)."""

    def __init__(self, http_client: httpx.AsyncClient, *, client_id: str, client_secret: str) -> None:
        self._http = http_client
        self._client_id = client_id
        self._client_secret = client_secret

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        """Build the Google consent-screen URL."""
        query = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(query)}"

    async def fetch_profile(self, *, code: str, redirect_uri: str) -> GoogleProfile:
        """Exchange the authorization code and read the signed-in user's profile."""
        tokens = await _post_json(
            self._http,
            GOOGLE_TOKEN_URL,
            {
                "code": code,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        access_token = tokens.get("access_token")
        if not access_token:
            raise OAuthFlowError("google_token_exchange_failed")
        info = await _get_json(self._http, GOOGLE_USERINFO_URL, access_token)
        if not info.get("sub") or not info.get("email"):
            raise OAuthFlowError("google_profile_incomplete")
        return GoogleProfile(
            sub=str(info["sub"]),
            email=str(info["email"]).lower(),
            email_verified=bool(info.get("email_verified")),
            name=str(info.get("name") or info["email"]),
            picture=info.get("picture"),
        )


class GitHubOAuthClient:
    """Authorization-code flow for connecting a GitHub account (OAuth App)."""

    def __init__(self, http_client: httpx.AsyncClient, *, client_id: str, client_secret: str, scopes: str) -> None:
        self._http = http_client
        self._client_id = client_id
        self._client_secret = client_secret
        self._scopes = scopes

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        """Build the GitHub authorization URL."""
        query = {"client_id": self._client_id, "redirect_uri": redirect_uri, "scope": self._scopes, "state": state}
        return f"{GITHUB_AUTHORIZE_URL}?{urlencode(query)}"

    async def exchange(self, *, code: str, redirect_uri: str) -> GitHubGrant:
        """Exchange the authorization code for a user token and look up the account login."""
        tokens = await _post_json(
            self._http,
            GITHUB_TOKEN_URL,
            {"client_id": self._client_id, "client_secret": self._client_secret, "code": code, "redirect_uri": redirect_uri},
        )
        access_token = tokens.get("access_token")
        if not access_token:
            raise OAuthFlowError("github_token_exchange_failed")
        user = await _get_json(self._http, f"{GITHUB_API_URL}/user", access_token)
        scopes = [scope for scope in str(tokens.get("scope") or "").split(",") if scope]
        return GitHubGrant(access_token=access_token, scopes=scopes, login=str(user.get("login") or ""))

    async def revoke(self, access_token: str) -> None:
        """Revoke Setu's authorization for this token on GitHub; failures are ignored."""
        try:
            await self._http.request(
                "DELETE",
                f"{GITHUB_API_URL}/applications/{self._client_id}/grant",
                auth=(self._client_id, self._client_secret),
                json={"access_token": access_token},
                headers={"Accept": "application/vnd.github+json"},
            )
        except httpx.HTTPError:
            pass


async def _post_json(http: httpx.AsyncClient, url: str, form: dict[str, str]) -> dict[str, Any]:
    """POST a form and return the JSON body, mapping any failure to a safe flow error."""
    try:
        response = await http.post(url, data=form, headers={"Accept": "application/json"})
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise OAuthFlowError("provider_unreachable") from error
    return body if isinstance(body, dict) else {}


async def _get_json(http: httpx.AsyncClient, url: str, access_token: str) -> dict[str, Any]:
    """GET a JSON resource with a bearer token."""
    try:
        response = await http.get(url, headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"})
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise OAuthFlowError("provider_unreachable") from error
    return body if isinstance(body, dict) else {}

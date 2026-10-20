"""Endpoint tests for Google sign-in and GitHub connection redirects using fake services."""

from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.api.v1.auth.dependencies import SESSION_COOKIE, get_auth_service, get_connection_service
from app.main import app
from app.modules.accounts.domain.models import Connection, OAuthFlowError, User


USER = User(id="u1", email="a@example.com", name="Asha")


class FakeAuth:
    google_enabled = True

    def __init__(self) -> None:
        self.signed_out: list[str] = []
        self.fail_with: str | None = None

    def google_authorization_url(self, *, state: str, redirect_uri: str) -> str:
        return f"https://accounts.google.test/auth?state={state}&redirect_uri={redirect_uri}"

    async def sign_in_with_google(self, *, code: str, redirect_uri: str) -> tuple[User, str]:
        if self.fail_with:
            raise OAuthFlowError(self.fail_with)
        return USER, "session-token"

    async def user_for_session(self, token: str) -> User | None:
        return USER if token == "session-token" else None

    async def sign_out(self, token: str) -> None:
        self.signed_out.append(token)


class FakeConnections:
    github_enabled = True

    def __init__(self) -> None:
        self.connected: list[str] = []
        self.disconnected: list[str] = []

    def github_authorization_url(self, *, state: str, redirect_uri: str) -> str:
        return f"https://github.test/authorize?state={state}"

    async def connect_github(self, user_id: str, *, code: str, redirect_uri: str) -> Connection:
        self.connected.append(user_id)
        return Connection(provider="github", account="octocat", scopes=[], connected_at=1)

    async def list_connections(self, user_id: str) -> list[Connection]:
        return [Connection(provider="github", account="octocat", scopes=["repo"], connected_at=1)] if self.connected else []

    async def disconnect_github(self, user_id: str) -> None:
        self.disconnected.append(user_id)


class AuthEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.auth = FakeAuth()
        self.connections = FakeConnections()
        app.dependency_overrides[get_auth_service] = lambda: self.auth
        app.dependency_overrides[get_connection_service] = lambda: self.connections
        self.client = TestClient(app, follow_redirects=False)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()

    def _sign_in(self) -> None:
        login = self.client.get("/api/v1/auth/google/login")
        state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
        callback = self.client.get("/api/v1/auth/google/callback", params={"code": "c", "state": state})
        self.assertEqual(callback.headers["location"], "http://localhost:5173/")

    def test_me_requires_a_session(self) -> None:
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "AUTH_REQUIRED")

    def test_google_round_trip_sets_session_cookie(self) -> None:
        self._sign_in()
        self.assertEqual(self.client.cookies.get(SESSION_COOKIE), "session-token")
        self.assertEqual(self.client.get("/api/v1/auth/me").json()["data"]["email"], "a@example.com")

    def test_callback_rejects_mismatched_state(self) -> None:
        self.client.get("/api/v1/auth/google/login")
        response = self.client.get("/api/v1/auth/google/callback", params={"code": "c", "state": "forged"})
        self.assertIn("auth_error=state_mismatch", response.headers["location"])
        self.assertIsNone(self.client.cookies.get(SESSION_COOKIE))

    def test_callback_reports_flow_errors(self) -> None:
        self.auth.fail_with = "email_not_allowed"
        login = self.client.get("/api/v1/auth/google/login")
        state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
        response = self.client.get("/api/v1/auth/google/callback", params={"code": "c", "state": state})
        self.assertIn("auth_error=email_not_allowed", response.headers["location"])

    def test_logout_ends_session(self) -> None:
        self._sign_in()
        self.client.post("/api/v1/auth/logout")
        self.assertEqual(self.auth.signed_out, ["session-token"])
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

    def test_github_connect_flow_and_listing(self) -> None:
        self._sign_in()
        self.assertFalse(self.client.get("/api/v1/connections").json()["data"][0]["connected"])

        login = self.client.get("/api/v1/connections/github/login")
        state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
        callback = self.client.get("/api/v1/connections/github/callback", params={"code": "c", "state": state})
        self.assertEqual(callback.headers["location"], "http://localhost:5173/?connected=github")
        self.assertEqual(self.connections.connected, ["u1"])
        self.assertEqual(self.client.get("/api/v1/connections").json()["data"][0]["account"], "octocat")

        self.client.delete("/api/v1/connections/github")
        self.assertEqual(self.connections.disconnected, ["u1"])

    def test_github_login_requires_sign_in(self) -> None:
        self.assertEqual(self.client.get("/api/v1/connections/github/login").status_code, 401)

    def test_config_reports_enabled_providers(self) -> None:
        data = self.client.get("/api/v1/auth/config").json()["data"]
        self.assertEqual(data, {"google_enabled": True, "github_enabled": True})

"""Tests for sign-in sessions and connected accounts against a temporary SQLite database."""

from __future__ import annotations

import tempfile
import time
import unittest

from sqlalchemy import select

from app.core.database import create_engine, create_session_factory, create_tables
from app.modules.accounts.application.auth import AuthService
from app.modules.accounts.application.connections import ConnectionService
from app.modules.accounts.domain.models import OAuthFlowError
from app.modules.accounts.infrastructure.oauth import GitHubGrant, GoogleProfile
from app.modules.accounts.infrastructure.records import ConnectionRecord
from app.modules.accounts.infrastructure.token_cipher import TokenCipher


class FakeGoogle:
    def __init__(self, profile: GoogleProfile) -> None:
        self.profile = profile

    async def fetch_profile(self, *, code: str, redirect_uri: str) -> GoogleProfile:
        return self.profile


class FakeGitHub:
    def __init__(self) -> None:
        self.revoked: list[str] = []

    async def exchange(self, *, code: str, redirect_uri: str) -> GitHubGrant:
        return GitHubGrant(access_token=f"gho_{code}", scopes=["read:user", "repo"], login="octocat")

    async def revoke(self, access_token: str) -> None:
        self.revoked.append(access_token)


def _profile(**changes: object) -> GoogleProfile:
    values: dict[str, object] = {"sub": "g-1", "email": "a@example.com", "email_verified": True, "name": "Asha", "picture": None}
    values.update(changes)
    return GoogleProfile(**values)  # type: ignore[arg-type]


class AccountServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite+aiosqlite:///{self._directory.name}/test.db")
        await create_tables(self.engine)
        self.sessions = create_session_factory(self.engine)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()
        self._directory.cleanup()

    def _auth(self, profile: GoogleProfile | None = None, *, ttl: int = 3600, allowed: list[str] | None = None) -> AuthService:
        return AuthService(self.sessions, FakeGoogle(profile or _profile()), session_ttl_seconds=ttl, allowed_emails=allowed or [])  # type: ignore[arg-type]

    async def test_sign_in_creates_user_and_resolvable_session(self) -> None:
        auth = self._auth()
        user, token = await auth.sign_in_with_google(code="c", redirect_uri="r")
        self.assertEqual((user.email, user.name), ("a@example.com", "Asha"))
        self.assertEqual(await auth.user_for_session(token), user)
        self.assertIsNone(await auth.user_for_session("not-a-token"))

    async def test_repeat_sign_in_reuses_user_and_updates_profile(self) -> None:
        first, _ = await self._auth().sign_in_with_google(code="c", redirect_uri="r")
        second, _ = await self._auth(_profile(name="Asha R")).sign_in_with_google(code="c", redirect_uri="r")
        self.assertEqual(first.id, second.id)
        self.assertEqual(second.name, "Asha R")

    async def test_sign_out_and_expiry_end_the_session(self) -> None:
        auth = self._auth()
        _, token = await auth.sign_in_with_google(code="c", redirect_uri="r")
        await auth.sign_out(token)
        self.assertIsNone(await auth.user_for_session(token))

        expired = self._auth(ttl=-1)
        _, old_token = await expired.sign_in_with_google(code="c", redirect_uri="r")
        self.assertIsNone(await expired.user_for_session(old_token))

    async def test_rejects_unverified_and_disallowed_emails(self) -> None:
        with self.assertRaises(OAuthFlowError) as unverified:
            await self._auth(_profile(email_verified=False)).sign_in_with_google(code="c", redirect_uri="r")
        self.assertEqual(unverified.exception.reason, "email_not_verified")
        with self.assertRaises(OAuthFlowError) as disallowed:
            await self._auth(allowed=["someone@else.com"]).sign_in_with_google(code="c", redirect_uri="r")
        self.assertEqual(disallowed.exception.reason, "email_not_allowed")

    async def test_github_connection_is_encrypted_per_user_and_revoked_on_disconnect(self) -> None:
        github = FakeGitHub()
        connections = ConnectionService(self.sessions, TokenCipher("secret"), github)  # type: ignore[arg-type]
        await connections.connect_github("u1", code="abc", redirect_uri="r")

        async with self.sessions() as db:
            stored = await db.scalar(select(ConnectionRecord))
        assert stored is not None
        self.assertNotIn("gho_abc", stored.encrypted_token)
        self.assertEqual(await connections.github_token("u1"), "gho_abc")
        self.assertIsNone(await connections.github_token("u2"))
        self.assertEqual([c.account for c in await connections.list_connections("u1")], ["octocat"])

        await connections.disconnect_github("u1")
        self.assertIsNone(await connections.github_token("u1"))
        self.assertEqual(github.revoked, ["gho_abc"])

    async def test_token_from_another_secret_reads_as_disconnected(self) -> None:
        await ConnectionService(self.sessions, TokenCipher("one"), FakeGitHub()).connect_github("u1", code="x", redirect_uri="r")  # type: ignore[arg-type]
        self.assertIsNone(await ConnectionService(self.sessions, TokenCipher("two"), None).github_token("u1"))

    async def test_connection_timestamp_is_recent(self) -> None:
        connection = await ConnectionService(self.sessions, TokenCipher("s"), FakeGitHub()).connect_github("u1", code="x", redirect_uri="r")  # type: ignore[arg-type]
        self.assertLessEqual(abs(connection.connected_at - int(time.time())), 5)

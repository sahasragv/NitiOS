"""Application service for third-party accounts a user links to Setu."""

from __future__ import annotations

import time

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.modules.accounts.domain.models import Connection, OAuthFlowError
from app.modules.accounts.infrastructure.oauth import GitHubOAuthClient
from app.modules.accounts.infrastructure.records import ConnectionRecord
from app.modules.accounts.infrastructure.token_cipher import TokenCipher


class ConnectionService:
    """Link, list and unlink a user's GitHub account; tokens are stored encrypted."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession], cipher: TokenCipher, github: GitHubOAuthClient | None) -> None:
        self._sessions = sessions
        self._cipher = cipher
        self._github = github
        self._logger = get_logger(__name__)

    @property
    def github_enabled(self) -> bool:
        """Whether GitHub OAuth credentials are configured."""
        return self._github is not None

    def github_authorization_url(self, *, state: str, redirect_uri: str) -> str:
        """Return the GitHub authorization URL; requires :attr:`github_enabled`."""
        if self._github is None:
            raise OAuthFlowError("github_not_configured")
        return self._github.authorization_url(state=state, redirect_uri=redirect_uri)

    async def connect_github(self, user_id: str, *, code: str, redirect_uri: str) -> Connection:
        """Complete the GitHub flow and store (or replace) the user's GitHub connection."""
        if self._github is None:
            raise OAuthFlowError("github_not_configured")
        grant = await self._github.exchange(code=code, redirect_uri=redirect_uri)
        now = int(time.time())
        async with self._sessions() as db, db.begin():
            await db.execute(delete(ConnectionRecord).where(ConnectionRecord.user_id == user_id, ConnectionRecord.provider == "github"))
            db.add(
                ConnectionRecord(
                    user_id=user_id,
                    provider="github",
                    account=grant.login,
                    scopes=",".join(grant.scopes),
                    encrypted_token=self._cipher.encrypt(grant.access_token),
                    connected_at=now,
                )
            )
        self._logger.info("GitHub connected | user_id=%s", user_id)
        return Connection(provider="github", account=grant.login, scopes=grant.scopes, connected_at=now)

    async def list_connections(self, user_id: str) -> list[Connection]:
        """Return the user's linked accounts without their tokens."""
        async with self._sessions() as db:
            records = (await db.scalars(select(ConnectionRecord).where(ConnectionRecord.user_id == user_id))).all()
        return [
            Connection(provider="github", account=record.account, scopes=[s for s in record.scopes.split(",") if s], connected_at=record.connected_at)
            for record in records
            if record.provider == "github"
        ]

    async def github_token(self, user_id: str) -> str | None:
        """Return the user's decrypted GitHub token, or ``None`` if not connected or unreadable."""
        async with self._sessions() as db:
            record = await db.scalar(
                select(ConnectionRecord).where(ConnectionRecord.user_id == user_id, ConnectionRecord.provider == "github")
            )
        if record is None:
            return None
        token = self._cipher.decrypt(record.encrypted_token)
        if token is None:
            self._logger.warning("Stored GitHub token could not be decrypted; was SECRET_KEY changed? | user_id=%s", user_id)
        return token

    async def disconnect_github(self, user_id: str) -> None:
        """Remove the user's GitHub connection and revoke Setu's access on GitHub."""
        token = await self.github_token(user_id)
        async with self._sessions() as db, db.begin():
            await db.execute(delete(ConnectionRecord).where(ConnectionRecord.user_id == user_id, ConnectionRecord.provider == "github"))
        if token and self._github is not None:
            await self._github.revoke(token)
        self._logger.info("GitHub disconnected | user_id=%s", user_id)

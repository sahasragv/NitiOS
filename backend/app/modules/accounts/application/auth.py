"""Application service for Google sign-in and browser sessions."""

from __future__ import annotations

import hashlib
import secrets
import time
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.modules.accounts.domain.models import OAuthFlowError, User
from app.modules.accounts.infrastructure.oauth import GoogleOAuthClient
from app.modules.accounts.infrastructure.records import SessionRecord, UserRecord


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _to_user(record: UserRecord) -> User:
    return User(id=record.id, email=record.email, name=record.name, picture=record.picture)


class AuthService:
    """Sign users in with Google and resolve session cookies to users."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        google: GoogleOAuthClient | None,
        *,
        session_ttl_seconds: int,
        allowed_emails: list[str],
    ) -> None:
        self._sessions = sessions
        self._google = google
        self._session_ttl = session_ttl_seconds
        self._allowed_emails = {email.strip().lower() for email in allowed_emails if email.strip()}
        self._logger = get_logger(__name__)

    @property
    def google_enabled(self) -> bool:
        """Whether Google OAuth credentials are configured."""
        return self._google is not None

    def google_authorization_url(self, *, state: str, redirect_uri: str) -> str:
        """Return the Google consent URL; requires :attr:`google_enabled`."""
        if self._google is None:
            raise OAuthFlowError("google_not_configured")
        return self._google.authorization_url(state=state, redirect_uri=redirect_uri)

    async def sign_in_with_google(self, *, code: str, redirect_uri: str) -> tuple[User, str]:
        """Complete the Google flow, create or update the user, and return a new session token."""
        if self._google is None:
            raise OAuthFlowError("google_not_configured")
        profile = await self._google.fetch_profile(code=code, redirect_uri=redirect_uri)
        if not profile.email_verified:
            raise OAuthFlowError("email_not_verified")
        if self._allowed_emails and profile.email not in self._allowed_emails:
            self._logger.warning("Sign-in refused for an email outside ALLOWED_EMAILS.")
            raise OAuthFlowError("email_not_allowed")

        now = int(time.time())
        token = secrets.token_urlsafe(32)
        async with self._sessions() as db, db.begin():
            record = await db.scalar(select(UserRecord).where(UserRecord.google_sub == profile.sub))
            if record is None:
                record = UserRecord(id=uuid4().hex, google_sub=profile.sub, created_at=now, email="", name="", last_login_at=now)
                db.add(record)
            record.email, record.name, record.picture, record.last_login_at = profile.email, profile.name, profile.picture, now
            db.add(SessionRecord(token_hash=_hash(token), user_id=record.id, created_at=now, expires_at=now + self._session_ttl))
            await db.execute(delete(SessionRecord).where(SessionRecord.expires_at < now))
        self._logger.info("User signed in | user_id=%s", record.id)
        return _to_user(record), token

    async def user_for_session(self, token: str) -> User | None:
        """Return the user behind a session token, or ``None`` if it is unknown or expired."""
        async with self._sessions() as db:
            row = await db.execute(
                select(UserRecord)
                .join(SessionRecord, SessionRecord.user_id == UserRecord.id)
                .where(SessionRecord.token_hash == _hash(token), SessionRecord.expires_at > int(time.time()))
            )
            record = row.scalar_one_or_none()
        return _to_user(record) if record else None

    async def sign_out(self, token: str) -> None:
        """Delete the session behind ``token``."""
        async with self._sessions() as db, db.begin():
            await db.execute(delete(SessionRecord).where(SessionRecord.token_hash == _hash(token)))

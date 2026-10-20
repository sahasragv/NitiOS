"""Database tables for users, sessions and connected accounts. Timestamps are Unix seconds."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRecord(Base):
    """A person who signed in with Google, keyed by Google's stable subject id."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    google_sub: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(320))
    name: Mapped[str] = mapped_column(String(255))
    picture: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[int] = mapped_column(Integer)
    last_login_at: Mapped[int] = mapped_column(Integer)


class SessionRecord(Base):
    """A browser sign-in session. Only a SHA-256 hash of the cookie value is stored."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[int] = mapped_column(Integer)


class ConnectionRecord(Base):
    """A linked third-party account with its access token encrypted at rest."""

    __tablename__ = "connections"
    __table_args__ = (UniqueConstraint("user_id", "provider"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    account: Mapped[str] = mapped_column(String(255))
    scopes: Mapped[str] = mapped_column(Text, default="")
    encrypted_token: Mapped[str] = mapped_column(Text)
    connected_at: Mapped[int] = mapped_column(Integer)

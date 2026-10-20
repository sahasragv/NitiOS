"""Async SQLAlchemy engine, session factory and declarative base."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base shared by every table."""


def create_engine(url: str) -> AsyncEngine:
    """Create the application engine for ``url``."""
    return create_async_engine(url)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a session factory whose objects stay readable after commit."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_tables(engine: AsyncEngine) -> None:
    """Create any missing tables; existing tables and rows are left untouched."""
    # Imported for its side effect of registering the tables on ``Base.metadata``.
    from app.modules.accounts.infrastructure import records  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

"""
NotesOS Database Configuration - Async SQLAlchemy Setup
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


# Create async engine
# pool_size + max_overflow kept small on purpose:
# API + grading worker + fact-check worker each create their own pool.
# 3 processes × (2+3)=5 = 15 connections max, well under Postgres's non-superuser limit.
engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=3,
    connect_args=settings.DB_CONNECT_ARGS,
)

# Create session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """Initialize database - create tables if they don't exist."""
    async with engine.begin() as conn:
        # Enable pgvector extension before creating tables
        from sqlalchemy import text
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # Import all models to ensure they're registered
        from app.models import (
            user,
            course,
            test,
            progress,
            resource,
            classmate,
        )

        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Dependency for getting database session (FastAPI Depends only)."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def worker_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions in background workers.

    Use this instead of `async for db in get_db()` in worker code.
    `get_db()` is a FastAPI dependency generator and must only be used
    via `Depends(get_db)` inside API routes.

    Usage:
        async with worker_session() as db:
            result = await db.execute(...)
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

"""
Shared pytest fixtures for the NotesOS backend test suite.

Strategy
--------
- A dedicated test database (TEST_DATABASE_URL) has its schema built once per
  session from the SQLAlchemy models (Base.metadata), not from Alembic
  migrations. This keeps the suite fast and lets the model definitions be the
  single source of truth the tests assert against. A separate migration
  smoke-test verifies Alembic head.
- Between tests every table is TRUNCATE ... RESTART IDENTITY CASCADE'd, so each
  test starts from a clean slate without paying for a full schema rebuild.
- Redis and outbound email are neutralised: caching is disabled and the welcome
  email is patched to a no-op, so the suite has no hard dependency on either.

Event-loop / connection safety
------------------------------
pytest-asyncio runs in ``auto`` mode with function-scoped event loops (the
default). asyncpg connections are pinned to the event loop that created them and
are NOT concurrency-safe. A session-scoped engine would build its pool on the
session-setup loop and then hand those connections to tests running on a
different (function) loop, producing
``InterfaceError: cannot perform operation: another operation is in progress``.

To avoid that entirely:
- The per-session schema build runs in its own isolated ``asyncio.run`` loop on a
  throwaway ``NullPool`` engine, so no connection outlives it.
- The ``engine`` used by tests is function-scoped and uses ``NullPool`` — every
  test gets fresh connections created on its own loop, and nothing survives past
  the test.
- ``db_session`` and the app (via ``get_db`` override) each draw their own
  ``AsyncSession`` from the same function-scoped factory, so no single asyncpg
  connection is ever shared between two coroutines.

Set TEST_DATABASE_URL to point at a local Postgres with the pgvector extension
available. Default assumes the docker-compose Postgres with a `notesos_test` db.
"""

import asyncio
import os
import uuid

# Neutralise external services BEFORE importing the app / settings.
os.environ.setdefault("CACHE_ENABLED", "false")
os.environ.setdefault("DATABASE_SSL", "false")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://notesos:blessed@localhost:5432/notesos_test",
)


def _db_name(url: str) -> str:
    return url.rsplit("/", 1)[-1].split("?", 1)[0]


def _assert_safe_test_database() -> None:
    """Hard stop before this session can touch TEST_DATABASE_URL at all.

    This fixture runs drop_all + create_all against TEST_DATABASE_URL every
    session. A misconfigured value that happens to point at the real dev/prod
    database silently wipes it — this has actually happened. "test" in the name
    is the one convention every real db in this repo violates, so it's a cheap,
    reliable tripwire; DATABASE_URL is checked explicitly on top of it.
    """
    name = _db_name(TEST_DATABASE_URL)
    dev_url = os.environ.get("DATABASE_URL", "")
    dev_name = _db_name(dev_url) if dev_url else None

    if name == dev_name:
        raise RuntimeError(
            f"REFUSING TO RUN: TEST_DATABASE_URL targets {name!r}, the same database "
            f"as DATABASE_URL. The test suite runs drop_all + create_all on "
            f"TEST_DATABASE_URL every session — this would wipe your dev database. "
            f"Point TEST_DATABASE_URL at a dedicated test database instead."
        )
    if "test" not in name.lower():
        raise RuntimeError(
            f"REFUSING TO RUN: TEST_DATABASE_URL targets {name!r}, which doesn't look "
            f"like a test database (expected 'test' in the name). The test suite runs "
            f"drop_all + create_all on this database every session. If this really is "
            f"a disposable test database, rename it to include 'test', or adjust this "
            f"check in conftest.py deliberately."
        )


_assert_safe_test_database()

# Importing app.models registers every model on Base.metadata.
import app.models  # noqa: F401,E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    """Build the schema once per session in a fully isolated event loop.

    Uses its own ``asyncio.run`` loop and a NullPool engine so no asyncpg
    connection outlives this call — nothing is shared with the per-test loops.
    """

    async def _build():
        eng = create_async_engine(TEST_DATABASE_URL, future=True, poolclass=NullPool)
        try:
            async with eng.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
        finally:
            await eng.dispose()

    asyncio.run(_build())
    yield


@pytest_asyncio.fixture
async def engine(_schema):
    """Function-scoped engine on a NullPool.

    A fresh engine per test means every connection is created on that test's own
    event loop and disposed with it — no cross-loop connection reuse.
    """
    eng = create_async_engine(TEST_DATABASE_URL, future=True, poolclass=NullPool)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(engine):
    """Wipe every table after each test for isolation."""
    yield
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    if tables:
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def _no_outbound_email(monkeypatch):
    """Register fires a welcome email as a background task; stub it."""
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.email.send_welcome_email", _noop, raising=False
    )


@pytest_asyncio.fixture
async def db_session(session_factory):
    """A raw session for tests that exercise models / DB constraints directly."""
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(session_factory):
    """HTTP client wired to the test database via a get_db override.

    The app gets its own AsyncSession per request from the same function-scoped
    factory, independent of any ``db_session`` the test also holds — so the app
    coroutine and the test body never touch the same asyncpg connection.
    """

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def unique_phone() -> str:
    """A fresh, already-normalized phone number for a test user."""
    return "+234" + str(uuid.uuid4().int)[:9]


@pytest_asyncio.fixture
async def register_user(client):
    """Factory: register a fresh phone-primary user with a password.

    Registration issues tokens immediately (no OTP step). Returns the same
    ``{id, headers, tokens}`` shape the rest of the suite relies on, plus
    ``phone``. Extra keyword args (school_name, program, entry_year, email)
    pass through to the register payload.
    """

    async def _make(
        phone: str | None = None,
        password: str = "password123",
        full_name: str = "Test User",
        email: str | None = None,
        **extra,
    ):
        phone = phone or unique_phone()
        payload = {"phone": phone, "password": password, "full_name": full_name}
        if email is not None:
            payload["email"] = email
        payload.update(extra)

        resp = await client.post("/api/auth/register", json=payload)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        return {
            "id": data["user"]["id"],
            "phone": phone,
            "email": email,
            "password": password,
            "tokens": data,
            "headers": {"Authorization": f"Bearer {data['access_token']}"},
        }

    return _make

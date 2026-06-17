"""Pytest configuration: async test database with file-based SQLite.

Uses aiosqlite with a temporary file to ensure all connections
(engine, schema creation, test sessions) share the same database.
"""

import asyncio
import os
import tempfile
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.models import Base as SA_Base





@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_file() -> str:
    """Create a temporary SQLite database file for the session."""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_smes_")
    os.close(fd)
    yield path
    # Cleanup after session
    if os.path.exists(path):
        os.unlink(path)


@pytest_asyncio.fixture(scope="session")
async def engine(db_file: str):
    """Create engine bound to the temp file; create all tables once."""
    url = f"sqlite+aiosqlite:///{db_file}"
    eng = create_async_engine(url, poolclass=NullPool, echo=False)

    # Create all tables
    async with eng.begin() as conn:
        await conn.run_sync(SA_Base.metadata.create_all)

    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a clean async session per test; data is rolled back.

    We use begin_nested (savepoint) so the schema persists across tests
    but test data is isolated.
    """
    connection = await engine.connect()
    transaction = await connection.begin()

    session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
    )

    yield session

    await session.close()
    await transaction.rollback()
    await connection.close()


# ---------------------------------------------------------------------------
# Sample data factories  (used across multiple test files)
# ---------------------------------------------------------------------------
from datetime import datetime
from app.models import (
    Customer,
    MaterialMaster,
    MaterialCategory,
    Shelf,
    ShelfSlot,
    InventoryPallet,
)


@pytest_asyncio.fixture
async def sample_customer(db_session: AsyncSession) -> Customer:
    """Create and return a sample customer."""
    c = Customer(name="测试客户", code="CUST001")
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


@pytest_asyncio.fixture
async def sample_category(
    db_session: AsyncSession, sample_customer: Customer
) -> MaterialCategory:
    """Create and return a sample material category."""
    cat = MaterialCategory(
        customer_id=sample_customer.id,
        name="电阻",
        code="RES",
    )
    db_session.add(cat)
    await db_session.commit()
    await db_session.refresh(cat)
    return cat


@pytest_asyncio.fixture
async def sample_material(
    db_session: AsyncSession,
    sample_customer: Customer,
    sample_category: MaterialCategory,
) -> MaterialMaster:
    """Create and return a sample material."""
    m = MaterialMaster(
        customer_id=sample_customer.id,
        category_id=sample_category.id,
        code="RES-100K",
        name="贴片电阻 100KΩ",
        unit="盘",
    )
    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)
    return m

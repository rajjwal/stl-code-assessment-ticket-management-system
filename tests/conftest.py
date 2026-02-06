"""Shared test fixtures for the CMDB test suite.

Provides in-memory SQLite database, async test client, and sample data loaders.
"""

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app

# Import models to ensure tables are registered with Base.metadata
import app.models  # noqa: F401

INPUT_DATA_DIR = Path(__file__).parent.parent / "input_data"


@pytest.fixture
async def db_engine():
    """Create an in-memory SQLite engine for isolated tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """Provide an async session bound to the in-memory database."""
    session_maker = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session


@pytest.fixture
async def client(db_engine):
    """Async HTTP test client with the test database injected."""
    session_maker = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def sample_hardware_json() -> bytes:
    """Load sample_hardware.json as bytes."""
    return (INPUT_DATA_DIR / "sample_hardware.json").read_bytes()


@pytest.fixture
def sample_hardware_csv() -> bytes:
    """Load sample_hardware.csv as bytes."""
    return (INPUT_DATA_DIR / "sample_hardware.csv").read_bytes()


@pytest.fixture
def sample_hardware_yaml() -> bytes:
    """Load sample_hardware.yaml as bytes."""
    return (INPUT_DATA_DIR / "sample_hardware.yaml").read_bytes()


@pytest.fixture
def sample_okta_json() -> bytes:
    """Load sample_okta.json as bytes."""
    return (INPUT_DATA_DIR / "sample_okta.json").read_bytes()


@pytest.fixture
def sample_app_json() -> bytes:
    """Load sample_app.json as bytes."""
    return (INPUT_DATA_DIR / "sample_app.json").read_bytes()

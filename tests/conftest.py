from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from cache_service.config import Settings
from cache_service.db import create_engine, create_session_factory, init_db
from cache_service.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # _env_file=None: a developer's local .env must not change how tests behave.
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        transformer_latency_seconds=0,
    )


@pytest.fixture
async def engine(settings: Settings) -> AsyncIterator[AsyncEngine]:
    db_engine = create_engine(settings.database_url)
    await init_db(db_engine)
    yield db_engine
    await db_engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest.fixture
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    # ASGITransport does not run lifespan events; LifespanManager does, like a real server.
    application = create_app(settings)
    async with LifespanManager(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http

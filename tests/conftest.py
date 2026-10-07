import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from cache_service.config import Settings
from cache_service.db import create_engine, create_session_factory, init_db
from cache_service.main import create_app
from tests.support import SpyTransformer, serve


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith(("CACHE_SERVICE_", "CACHE_CLI_")):
            monkeypatch.delenv(key)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        transformer_latency_seconds=0,
    )


@pytest.fixture
def spy() -> SpyTransformer:
    return SpyTransformer()


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
async def client(settings: Settings, spy: SpyTransformer) -> AsyncIterator[AsyncClient]:
    async with serve(create_app(settings, transformer=spy)) as http:
        yield http

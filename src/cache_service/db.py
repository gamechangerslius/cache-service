from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from cache_service.models import Base


def create_engine(database_url: str) -> AsyncEngine:
    url = make_url(database_url)
    engine = create_async_engine(url)
    if url.get_backend_name() == "sqlite":
        if url.database and url.database != ":memory:":
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
        event.listen(engine.sync_engine, "connect", _configure_sqlite_connection)
    return engine


def _configure_sqlite_connection(dbapi_connection: Any, _: Any) -> None:
    cursor = dbapi_connection.cursor()
    # WAL lets readers run during a write; busy_timeout makes concurrent writers wait, not fail.
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

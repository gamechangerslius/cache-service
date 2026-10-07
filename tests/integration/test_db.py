from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from cache_service.db import create_engine, init_db


async def test_init_db_creates_missing_directory_and_tables(tmp_path: Path) -> None:
    database = tmp_path / "nested" / "dir" / "cache.db"
    engine = create_engine(f"sqlite+aiosqlite:///{database}")

    await init_db(engine)
    async with engine.connect() as connection:
        tables = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
    await engine.dispose()

    assert database.exists()
    assert set(tables) == {"payloads", "transformations"}


async def test_connections_use_wal_and_wait_for_locks(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        journal_mode = await connection.scalar(text("PRAGMA journal_mode"))
        busy_timeout = await connection.scalar(text("PRAGMA busy_timeout"))

    assert journal_mode == "wal"
    assert busy_timeout == 5000

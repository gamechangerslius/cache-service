from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import QueuePool

from cache_service.cache import CachedTransformer
from cache_service.schemas import PayloadCreate
from cache_service.service import PayloadService


async def test_create_holds_no_connection_while_transforming(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    pool = engine.pool
    assert isinstance(pool, QueuePool)
    checked_out: list[int] = []

    async def probe(text: str, /) -> str:
        checked_out.append(pool.checkedout())
        return text.upper()

    service = PayloadService(
        session_factory, CachedTransformer(probe, session_factory, max_concurrency=1)
    )

    await service.create(PayloadCreate(list_1=["a"], list_2=["b"]))

    assert checked_out == [0, 0]

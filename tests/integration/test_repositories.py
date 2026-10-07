from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cache_service.repositories import PayloadRepository, TransformationRepository


async def test_get_many_returns_only_stored_texts(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = TransformationRepository(session)
        await repository.add_many({"a": "A", "b": "B"})

        await repository.add_many({})

        assert await repository.get_many(["a", "b", "c"]) == {"a": "A", "b": "B"}
        assert await repository.get_many([]) == {}


async def test_add_many_keeps_the_first_stored_output(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = TransformationRepository(session)
        await repository.add_many({"a": "A"})
        await repository.add_many({"a": "other", "b": "B"})
        await session.commit()

    async with session_factory() as session:
        stored = await TransformationRepository(session).get_many(["a", "b"])

    assert stored == {"a": "A", "b": "B"}


async def test_create_if_absent_reuses_the_id_for_the_same_hash(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = PayloadRepository(session)

        first_id, first_created = await repository.create_if_absent("hash", "OUTPUT")
        second_id, second_created = await repository.create_if_absent("hash", "OUTPUT")

    assert (first_created, second_created) == (True, False)
    assert second_id == first_id


async def test_payload_lookups(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        repository = PayloadRepository(session)
        payload_id, _ = await repository.create_if_absent("hash", "OUTPUT")

        assert await repository.get_output(payload_id) == "OUTPUT"
        assert await repository.get_output(uuid4()) is None
        assert await repository.get_id_by_hash("hash") == payload_id
        assert await repository.get_id_by_hash("unknown") is None

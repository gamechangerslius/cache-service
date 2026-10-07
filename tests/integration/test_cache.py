import asyncio
from collections.abc import Iterable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cache_service.cache import CachedTransformer, TransformResult
from cache_service.transformer import TransformerError
from tests.support import SpyTransformer

SessionFactory = async_sessionmaker[AsyncSession]


async def transform(
    session_factory: SessionFactory, cached: CachedTransformer, texts: Iterable[str]
) -> TransformResult:
    async with session_factory() as session:
        result = await cached.transform_many(session, texts)
        await session.commit()
        return result


@pytest.fixture
def cached(spy: SpyTransformer) -> CachedTransformer:
    return CachedTransformer(spy, max_concurrency=10)


async def test_cold_cache_transforms_each_distinct_string_once(
    session_factory: SessionFactory, cached: CachedTransformer, spy: SpyTransformer
) -> None:
    result = await transform(session_factory, cached, ["a", "b", "a"])

    assert result == TransformResult(outputs={"a": "A", "b": "B"}, cache_hits=0, cache_misses=2)
    assert spy.calls == {"a": 1, "b": 1}


async def test_warm_cache_skips_the_transformer(
    session_factory: SessionFactory, cached: CachedTransformer, spy: SpyTransformer
) -> None:
    await transform(session_factory, cached, ["a", "b"])
    spy.calls.clear()

    result = await transform(session_factory, cached, ["b", "a"])

    assert result == TransformResult(outputs={"a": "A", "b": "B"}, cache_hits=2, cache_misses=0)
    assert not spy.calls


async def test_only_new_strings_reach_the_transformer(
    session_factory: SessionFactory, cached: CachedTransformer, spy: SpyTransformer
) -> None:
    await transform(session_factory, cached, ["a", "b"])

    result = await transform(session_factory, cached, ["b", "c"])

    assert result.outputs == {"b": "B", "c": "C"}
    assert spy.calls == {"a": 1, "b": 1, "c": 1}


async def test_cache_lives_in_the_database_not_in_memory(
    session_factory: SessionFactory, cached: CachedTransformer
) -> None:
    await transform(session_factory, cached, ["a"])
    fresh_spy = SpyTransformer()

    await transform(session_factory, CachedTransformer(fresh_spy, max_concurrency=1), ["a"])

    assert not fresh_spy.calls


async def test_concurrent_transformer_calls_are_bounded(session_factory: SessionFactory) -> None:
    spy = SpyTransformer(delay=0.01)

    await transform(session_factory, CachedTransformer(spy, max_concurrency=2), list("abcdef"))

    assert spy.max_active == 2


async def test_failures_are_reported_and_successes_are_kept(
    session_factory: SessionFactory, cached: CachedTransformer, spy: SpyTransformer
) -> None:
    spy.fail_on = {"b"}
    async with session_factory() as session:
        with pytest.raises(TransformerError, match="1 of 2"):
            await cached.transform_many(session, ["a", "b"])
        await session.commit()
    spy.fail_on.clear()

    result = await transform(session_factory, cached, ["a", "b"])

    assert result.outputs == {"a": "A", "b": "B"}
    assert spy.calls == {"a": 1, "b": 2}


async def test_concurrent_requests_share_one_call_per_string(
    session_factory: SessionFactory,
) -> None:
    spy = SpyTransformer(delay=0.05)
    cached = CachedTransformer(spy, max_concurrency=10)

    first, second = await asyncio.gather(
        transform(session_factory, cached, ["a", "b"]),
        transform(session_factory, cached, ["b", "c"]),
    )

    assert first.outputs == {"a": "A", "b": "B"}
    assert second.outputs == {"b": "B", "c": "C"}
    assert spy.calls == {"a": 1, "b": 1, "c": 1}


async def test_cancelled_request_does_not_cancel_a_shared_call(
    session_factory: SessionFactory,
) -> None:
    spy = SpyTransformer(delay=0.2)
    cached = CachedTransformer(spy, max_concurrency=10)
    leader = asyncio.create_task(transform(session_factory, cached, ["a"]))
    await asyncio.sleep(0.05)
    follower = asyncio.create_task(transform(session_factory, cached, ["a"]))
    await asyncio.sleep(0.05)

    leader.cancel()
    result = await follower

    assert result.outputs == {"a": "A"}
    assert spy.calls == {"a": 1}

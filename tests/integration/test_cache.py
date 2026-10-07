import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cache_service.cache import CachedTransformer, TransformResult
from cache_service.repositories import TransformationRepository
from cache_service.transformer import TransformerError
from tests.support import SpyTransformer

SessionFactory = async_sessionmaker[AsyncSession]


@pytest.fixture
def cached(spy: SpyTransformer, session_factory: SessionFactory) -> CachedTransformer:
    return CachedTransformer(spy, session_factory, max_concurrency=10)


async def test_cold_cache_transforms_each_distinct_string_once(
    cached: CachedTransformer, spy: SpyTransformer
) -> None:
    result = await cached.transform_many(["a", "b", "a"])

    assert result == TransformResult(
        outputs={"a": "A", "b": "B"}, cache_hits=0, transformer_calls=2
    )
    assert spy.calls == {"a": 1, "b": 1}


async def test_warm_cache_skips_the_transformer(
    cached: CachedTransformer, spy: SpyTransformer
) -> None:
    await cached.transform_many(["a", "b"])
    spy.calls.clear()

    result = await cached.transform_many(["b", "a"])

    assert result == TransformResult(
        outputs={"a": "A", "b": "B"}, cache_hits=2, transformer_calls=0
    )
    assert not spy.calls


async def test_only_new_strings_reach_the_transformer(
    cached: CachedTransformer, spy: SpyTransformer
) -> None:
    await cached.transform_many(["a", "b"])

    result = await cached.transform_many(["b", "c"])

    assert result.outputs == {"b": "B", "c": "C"}
    assert spy.calls == {"a": 1, "b": 1, "c": 1}


async def test_cache_lives_in_the_database_not_in_memory(
    session_factory: SessionFactory, cached: CachedTransformer
) -> None:
    await cached.transform_many(["a"])
    fresh_spy = SpyTransformer()

    await CachedTransformer(fresh_spy, session_factory, max_concurrency=1).transform_many(["a"])

    assert not fresh_spy.calls


async def test_concurrent_transformer_calls_are_bounded(session_factory: SessionFactory) -> None:
    spy = SpyTransformer(delay=0.01)

    await CachedTransformer(spy, session_factory, max_concurrency=2).transform_many(list("abcdef"))

    assert spy.max_active == 2


async def test_failures_are_reported_and_successes_are_kept(
    cached: CachedTransformer, spy: SpyTransformer
) -> None:
    spy.fail_on = {"b"}
    with pytest.raises(TransformerError, match="1 of 2"):
        await cached.transform_many(["a", "b"])
    spy.fail_on.clear()

    result = await cached.transform_many(["a", "b"])

    assert result.outputs == {"a": "A", "b": "B"}
    assert spy.calls == {"a": 1, "b": 2}


async def test_concurrent_requests_share_one_call_per_string(
    session_factory: SessionFactory,
) -> None:
    spy = SpyTransformer(delay=0.05)
    cached = CachedTransformer(spy, session_factory, max_concurrency=10)

    first, second = await asyncio.gather(
        cached.transform_many(["a", "b"]), cached.transform_many(["b", "c"])
    )

    assert first.outputs == {"a": "A", "b": "B"}
    assert second.outputs == {"b": "B", "c": "C"}
    assert spy.calls == {"a": 1, "b": 1, "c": 1}
    assert first.transformer_calls + second.transformer_calls == 3


async def test_strings_finished_early_are_reused_by_later_requests(
    session_factory: SessionFactory,
) -> None:
    spy = SpyTransformer(delay=0.2)
    cached = CachedTransformer(spy, session_factory, max_concurrency=2)
    first = asyncio.create_task(cached.transform_many(list("abcdef")))
    await asyncio.sleep(0.3)

    second = await cached.transform_many(["a", "b"])
    await first

    assert second == TransformResult(
        outputs={"a": "A", "b": "B"}, cache_hits=2, transformer_calls=0
    )
    assert spy.calls.total() == 6


async def test_rechecks_the_database_before_calling_the_transformer(
    session_factory: SessionFactory,
) -> None:
    spy = SpyTransformer(delay=0.1)
    cached = CachedTransformer(spy, session_factory, max_concurrency=1)
    request = asyncio.create_task(cached.transform_many(["a", "b"]))
    await asyncio.sleep(0.05)
    async with session_factory.begin() as session:
        await TransformationRepository(session).add_many({"b": "stored elsewhere"})

    result = await request

    assert result == TransformResult(
        outputs={"a": "A", "b": "stored elsewhere"}, cache_hits=0, transformer_calls=1
    )
    assert spy.calls == {"a": 1}


async def test_cancelled_request_does_not_cancel_a_shared_call(
    session_factory: SessionFactory,
) -> None:
    spy = SpyTransformer(delay=0.2)
    cached = CachedTransformer(spy, session_factory, max_concurrency=10)
    leader = asyncio.create_task(cached.transform_many(["a"]))
    await asyncio.sleep(0.05)
    follower = asyncio.create_task(cached.transform_many(["a"]))
    await asyncio.sleep(0.05)

    leader.cancel()
    result = await follower

    assert result.outputs == {"a": "A"}
    assert spy.calls == {"a": 1}


async def test_unexpected_errors_are_not_reported_as_transformer_failures(
    session_factory: SessionFactory,
) -> None:
    async def broken(text: str, /) -> str:
        raise ValueError("bug in the client")

    cached = CachedTransformer(broken, session_factory, max_concurrency=1)

    with pytest.raises(ValueError, match="bug in the client"):
        await cached.transform_many(["a"])

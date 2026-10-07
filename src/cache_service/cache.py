import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cache_service.repositories import TransformationRepository
from cache_service.transformer import Transformer, TransformerError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TransformResult:
    outputs: dict[str, str]
    cache_hits: int
    transformer_calls: int


class CachedTransformer:
    def __init__(
        self,
        transformer: Transformer,
        session_factory: async_sessionmaker[AsyncSession],
        max_concurrency: int,
    ) -> None:
        self._transformer = transformer
        self._session_factory = session_factory
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._in_flight: dict[str, asyncio.Task[tuple[str, bool]]] = {}

    async def transform_many(self, texts: Iterable[str]) -> TransformResult:
        unique = list(dict.fromkeys(texts))
        async with self._session_factory() as session:
            outputs = await TransformationRepository(session).get_many(unique)
        cache_hits = len(outputs)
        misses = [text for text in unique if text not in outputs]

        outcomes = await asyncio.gather(
            *(self._transform(text) for text in misses), return_exceptions=True
        )
        failed = 0
        transformer_calls = 0
        for text, outcome in zip(misses, outcomes, strict=True):
            if isinstance(outcome, BaseException):
                logger.warning("transformer failed for %r", text, exc_info=outcome)
                failed += 1
            else:
                output, called = outcome
                outputs[text] = output
                transformer_calls += called

        if failed:
            raise TransformerError(f"{failed} of {len(misses)} strings could not be transformed")
        return TransformResult(
            outputs=outputs, cache_hits=cache_hits, transformer_calls=transformer_calls
        )

    async def _transform(self, text: str) -> tuple[str, bool]:
        task = self._in_flight.get(text)
        owner = task is None
        if task is None:
            task = asyncio.create_task(self._fetch(text))
            self._in_flight[text] = task
            task.add_done_callback(lambda _: self._in_flight.pop(text, None))
        output, called = await asyncio.shield(task)
        return output, owner and called

    async def _fetch(self, text: str) -> tuple[str, bool]:
        async with self._semaphore:
            async with self._session_factory() as session:
                stored = (await TransformationRepository(session).get_many([text])).get(text)
            if stored is not None:
                return stored, False
            output = await self._transformer(text)
            async with self._session_factory.begin() as session:
                await TransformationRepository(session).add_many({text: output})
        return output, True

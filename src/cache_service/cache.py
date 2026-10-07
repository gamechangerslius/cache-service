import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from cache_service.repositories import TransformationRepository
from cache_service.transformer import Transformer, TransformerError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TransformResult:
    outputs: dict[str, str]
    cache_hits: int
    cache_misses: int


class CachedTransformer:
    def __init__(self, transformer: Transformer, max_concurrency: int) -> None:
        self._transformer = transformer
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._in_flight: dict[str, asyncio.Task[str]] = {}

    async def transform_many(self, session: AsyncSession, texts: Iterable[str]) -> TransformResult:
        unique = list(dict.fromkeys(texts))
        repository = TransformationRepository(session)
        cached = await repository.get_many(unique)
        misses = [text for text in unique if text not in cached]

        outcomes = await asyncio.gather(
            *(self._transform(text) for text in misses), return_exceptions=True
        )
        computed: dict[str, str] = {}
        for text, outcome in zip(misses, outcomes, strict=True):
            if isinstance(outcome, BaseException):
                logger.warning("transformer failed for %r", text, exc_info=outcome)
            else:
                computed[text] = outcome

        await repository.add_many(computed)
        if len(computed) < len(misses):
            failed = len(misses) - len(computed)
            raise TransformerError(f"{failed} of {len(misses)} strings could not be transformed")
        return TransformResult(
            outputs=cached | computed, cache_hits=len(cached), cache_misses=len(misses)
        )

    async def _transform(self, text: str) -> str:
        task = self._in_flight.get(text)
        if task is None:
            task = asyncio.create_task(self._call_transformer(text))
            self._in_flight[text] = task
            task.add_done_callback(lambda _: self._in_flight.pop(text, None))
        return await asyncio.shield(task)

    async def _call_transformer(self, text: str) -> str:
        async with self._semaphore:
            return await self._transformer(text)

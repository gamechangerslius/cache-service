import asyncio
import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class Transformer(Protocol):
    async def __call__(self, text: str, /) -> str: ...


class SimulatedTransformer:
    def __init__(self, latency_seconds: float) -> None:
        self._latency_seconds = latency_seconds

    async def __call__(self, text: str, /) -> str:
        logger.debug("transforming %r", text)
        await asyncio.sleep(self._latency_seconds)
        return text.upper()

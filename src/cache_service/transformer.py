"""The "external" string transformer whose results the service caches.

It is simulated here; the ``Transformer`` protocol is where a real client would plug in.
"""

import asyncio
import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class Transformer(Protocol):
    """Asynchronously maps one string to its transformed form."""

    async def __call__(self, text: str, /) -> str: ...


class SimulatedTransformer:
    """Stands in for a slow remote service: uppercases ``text`` after a fixed delay.

    The delay makes the cache's effect observable, and is why cache misses are
    transformed concurrently rather than one after another.
    """

    def __init__(self, latency_seconds: float) -> None:
        self._latency_seconds = latency_seconds

    async def __call__(self, text: str, /) -> str:
        logger.debug("transforming %r", text)
        await asyncio.sleep(self._latency_seconds)
        return text.upper()

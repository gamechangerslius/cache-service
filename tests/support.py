import asyncio
from collections import Counter
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager

from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


class SpyTransformer:
    def __init__(self, *, delay: float = 0, fail_on: Iterable[str] = ()) -> None:
        self.calls: Counter[str] = Counter()
        self.delay = delay
        self.fail_on = set(fail_on)
        self.active = 0
        self.max_active = 0

    async def __call__(self, text: str, /) -> str:
        self.calls[text] += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(self.delay)
        finally:
            self.active -= 1
        if text in self.fail_on:
            raise RuntimeError(f"cannot transform {text!r}")
        return text.upper()


@asynccontextmanager
async def serve(app: FastAPI) -> AsyncIterator[AsyncClient]:
    # ASGITransport does not run lifespan events; LifespanManager does, like a real server.
    async with (
        LifespanManager(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client

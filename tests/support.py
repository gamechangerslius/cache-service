import asyncio
import threading
import time
from collections import Counter
from collections.abc import AsyncIterator, Iterable, Iterator
from contextlib import asynccontextmanager, contextmanager

import uvicorn
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from cache_service.transformer import TransformerError


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
            raise TransformerError(f"cannot transform {text!r}")
        return text.upper()


@asynccontextmanager
async def serve(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with (
        LifespanManager(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


@contextmanager
def live_server(app: FastAPI) -> Iterator[str]:
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError("test server did not start")
        time.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join()

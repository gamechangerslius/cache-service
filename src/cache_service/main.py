import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from cache_service import __version__
from cache_service.api import router
from cache_service.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        _configure_logging(resolved.log_level)
        yield

    app = FastAPI(title="Cache Service", version=__version__, lifespan=lifespan)
    app.state.settings = resolved
    app.include_router(router)
    return app


def _configure_logging(level: str) -> None:
    # Uvicorn configures only its own loggers; without a root handler our records are dropped.
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("cache_service").setLevel(level)

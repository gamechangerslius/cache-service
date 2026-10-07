import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from cache_service import __version__
from cache_service.api import router
from cache_service.config import Settings
from cache_service.db import create_engine, create_session_factory, init_db


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _configure_logging(resolved.log_level)
        engine = create_engine(resolved.database_url)
        await init_db(engine)
        app.state.session_factory = create_session_factory(engine)
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Cache Service", version=__version__, lifespan=lifespan)
    app.state.settings = resolved
    app.include_router(router)
    return app


def _configure_logging(level: str) -> None:
    # Uvicorn configures only its own loggers; without a root handler our records are dropped.
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("cache_service").setLevel(level)

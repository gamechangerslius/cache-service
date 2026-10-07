"""Application factory: builds the FastAPI app and owns its startup and shutdown."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from cache_service import __version__
from cache_service.api import router
from cache_service.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application.

    A factory instead of a module-level ``app`` keeps importing the package free of side
    effects (such as reading ``.env``) and lets each test run an app with its own settings.
    Serve it with ``uvicorn --factory cache_service.main:create_app``.
    """
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
    # Uvicorn configures only its own loggers, so without a root handler our INFO records
    # would be dropped. basicConfig is a no-op if the root logger is already set up elsewhere.
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("cache_service").setLevel(level)

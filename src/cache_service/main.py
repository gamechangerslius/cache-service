import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from cache_service import __version__
from cache_service.api import router
from cache_service.cache import CachedTransformer
from cache_service.config import Settings
from cache_service.db import create_engine, create_session_factory, init_db
from cache_service.transformer import SimulatedTransformer, Transformer


def create_app(
    settings: Settings | None = None, *, transformer: Transformer | None = None
) -> FastAPI:
    resolved = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _configure_logging(resolved.log_level)
        engine = create_engine(resolved.database_url)
        await init_db(engine)
        session_factory = create_session_factory(engine)
        app.state.session_factory = session_factory
        app.state.cached_transformer = CachedTransformer(
            transformer or SimulatedTransformer(resolved.transformer_latency_seconds),
            session_factory,
            max_concurrency=resolved.transformer_max_concurrency,
        )
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Cache Service", version=__version__, lifespan=lifespan)
    app.include_router(router)

    @app.exception_handler(RequestValidationError)
    async def validation_failed(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _AsciiJSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": jsonable_encoder(exc.errors())},
        )

    return app


class _AsciiJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(content, allow_nan=False, separators=(",", ":")).encode("ascii")


def _configure_logging(level: str) -> None:
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("cache_service").setLevel(level)

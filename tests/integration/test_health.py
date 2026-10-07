from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from cache_service.config import Settings
from cache_service.db import create_session_factory
from cache_service.main import create_app
from tests.support import SpyTransformer, serve


async def test_health_reports_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_reports_an_unavailable_database(
    settings: Settings, spy: SpyTransformer
) -> None:
    app = create_app(settings, transformer=spy)
    unreachable = create_async_engine("sqlite+aiosqlite:////nonexistent/dir/cache.db")

    async with serve(app) as client:
        app.state.session_factory = create_session_factory(unreachable)
        response = await client.get("/health")
    await unreachable.dispose()

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}

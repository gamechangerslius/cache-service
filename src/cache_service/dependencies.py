from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cache_service.cache import CachedTransformer
from cache_service.service import PayloadService


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_payload_service(request: Request, session: SessionDep) -> PayloadService:
    cached_transformer: CachedTransformer = request.app.state.cached_transformer
    return PayloadService(session, cached_transformer)


PayloadServiceDep = Annotated[PayloadService, Depends(get_payload_service)]

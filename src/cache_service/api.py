from fastapi import APIRouter
from sqlalchemy import text

from cache_service.dependencies import SessionDep
from cache_service.schemas import HealthResponse

router = APIRouter()


@router.get("/health", tags=["ops"], summary="Liveness check, including the database")
async def health(session: SessionDep) -> HealthResponse:
    await session.execute(text("SELECT 1"))
    return HealthResponse(status="ok")

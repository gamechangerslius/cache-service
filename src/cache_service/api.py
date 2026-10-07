from fastapi import APIRouter

from cache_service.schemas import HealthResponse

router = APIRouter()


@router.get("/health", tags=["ops"], summary="Liveness check")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")

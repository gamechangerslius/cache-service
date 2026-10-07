from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import text

from cache_service.dependencies import PayloadServiceDep, SessionDep
from cache_service.schemas import HealthResponse, PayloadCreate, PayloadCreated, PayloadRead
from cache_service.service import PayloadNotFoundError
from cache_service.transformer import TransformerError

router = APIRouter()


@router.post(
    "/payload",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_200_OK: {
            "model": PayloadCreated,
            "description": "The same payload was generated before",
        },
        status.HTTP_502_BAD_GATEWAY: {"description": "The transformer service failed"},
    },
    tags=["payloads"],
    summary="Generate a payload, or return the id of an identical one",
)
async def create_payload(
    body: PayloadCreate, service: PayloadServiceDep, request: Request, response: Response
) -> PayloadCreated:
    try:
        result = await service.create(body)
    except TransformerError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Transformer service failed") from exc

    if not result.created:
        response.status_code = status.HTTP_200_OK
        return PayloadCreated(id=result.id, message="Payload already exists")
    response.headers["Location"] = str(
        request.app.url_path_for("read_payload", payload_id=str(result.id))
    )
    return PayloadCreated(id=result.id, message="Payload created")


@router.get(
    "/payload/{payload_id}",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Unknown payload id"}},
    tags=["payloads"],
    summary="Read a generated payload",
)
async def read_payload(payload_id: UUID, service: PayloadServiceDep) -> PayloadRead:
    try:
        output = await service.get_output(payload_id)
    except PayloadNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payload not found") from exc
    return PayloadRead(output=output)


@router.get("/health", tags=["ops"], summary="Liveness check, including the database")
async def health(session: SessionDep) -> HealthResponse:
    await session.execute(text("SELECT 1"))
    return HealthResponse(status="ok")

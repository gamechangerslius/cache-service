import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cache_service.cache import CachedTransformer
from cache_service.payloads import fingerprint, interleave, render_output
from cache_service.repositories import PayloadRepository
from cache_service.schemas import PayloadCreate

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CreatedPayload:
    id: UUID
    created: bool


class PayloadNotFoundError(Exception):
    pass


class PayloadService:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], transformer: CachedTransformer
    ) -> None:
        self._session_factory = session_factory
        self._transformer = transformer

    async def create(self, request: PayloadCreate) -> CreatedPayload:
        inputs_hash = fingerprint(request.list_1, request.list_2)
        async with self._session_factory() as session:
            existing_id = await PayloadRepository(session).get_id_by_hash(inputs_hash)
        if existing_id is not None:
            logger.info("payload reused id=%s", existing_id)
            return CreatedPayload(existing_id, created=False)

        result = await self._transformer.transform_many([*request.list_1, *request.list_2])
        outputs = result.outputs
        output = render_output(
            interleave(
                [outputs[text] for text in request.list_1],
                [outputs[text] for text in request.list_2],
            )
        )
        async with self._session_factory.begin() as session:
            payload_id, created = await PayloadRepository(session).create_if_absent(
                inputs_hash, output
            )
        logger.info(
            "payload %s id=%s cache_hits=%d transformer_calls=%d",
            "created" if created else "reused",
            payload_id,
            result.cache_hits,
            result.transformer_calls,
        )
        return CreatedPayload(payload_id, created)

    async def get_output(self, payload_id: UUID) -> str:
        async with self._session_factory() as session:
            output = await PayloadRepository(session).get_output(payload_id)
        if output is None:
            raise PayloadNotFoundError(payload_id)
        return output

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from cache_service.cache import CachedTransformer
from cache_service.payloads import fingerprint, interleave, render_output
from cache_service.repositories import PayloadRepository
from cache_service.schemas import PayloadCreate
from cache_service.transformer import TransformerError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CreatedPayload:
    id: UUID
    created: bool


class PayloadNotFoundError(Exception):
    pass


class PayloadService:
    def __init__(self, session: AsyncSession, transformer: CachedTransformer) -> None:
        self._session = session
        self._transformer = transformer
        self._payloads = PayloadRepository(session)

    async def create(self, request: PayloadCreate) -> CreatedPayload:
        inputs_hash = fingerprint(request.list_1, request.list_2)
        existing_id = await self._payloads.get_id_by_hash(inputs_hash)
        if existing_id is not None:
            logger.info("payload reused id=%s", existing_id)
            return CreatedPayload(existing_id, created=False)

        try:
            result = await self._transformer.transform_many(
                self._session, [*request.list_1, *request.list_2]
            )
        except TransformerError:
            await self._session.commit()
            raise

        outputs = result.outputs
        output = render_output(
            interleave(
                [outputs[text] for text in request.list_1],
                [outputs[text] for text in request.list_2],
            )
        )
        payload_id, created = await self._payloads.create_if_absent(inputs_hash, output)
        await self._session.commit()
        logger.info(
            "payload %s id=%s cache_hits=%d cache_misses=%d",
            "created" if created else "reused",
            payload_id,
            result.cache_hits,
            result.cache_misses,
        )
        return CreatedPayload(payload_id, created)

    async def get_output(self, payload_id: UUID) -> str:
        output = await self._payloads.get_output(payload_id)
        if output is None:
            raise PayloadNotFoundError(payload_id)
        return output

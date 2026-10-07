from collections.abc import Collection, Mapping
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from cache_service.models import Payload, Transformation


class TransformationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_many(self, texts: Collection[str]) -> dict[str, str]:
        if not texts:
            return {}
        rows = await self._session.execute(
            select(Transformation.input_text, Transformation.output_text).where(
                Transformation.input_text.in_(texts)
            )
        )
        return {input_text: output_text for input_text, output_text in rows}

    async def add_many(self, outputs: Mapping[str, str]) -> None:
        if not outputs:
            return
        # A concurrent request may have stored the same string; its result is identical.
        statement = (
            insert(Transformation)
            .values([{"input_text": text, "output_text": out} for text, out in outputs.items()])
            .on_conflict_do_nothing(index_elements=[Transformation.input_text])
        )
        await self._session.execute(statement)


class PayloadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_output(self, payload_id: UUID) -> str | None:
        return await self._session.scalar(select(Payload.output).where(Payload.id == payload_id))

    async def get_id_by_hash(self, inputs_hash: str) -> UUID | None:
        return await self._session.scalar(
            select(Payload.id).where(Payload.inputs_hash == inputs_hash)
        )

    async def create_if_absent(self, inputs_hash: str, output: str) -> tuple[UUID, bool]:
        statement = (
            insert(Payload)
            .values(id=uuid4(), inputs_hash=inputs_hash, output=output)
            .on_conflict_do_nothing(index_elements=[Payload.inputs_hash])
            .returning(Payload.id)
        )
        created_id = await self._session.scalar(statement)
        if created_id is not None:
            return created_id, True
        existing = await self._session.execute(
            select(Payload.id).where(Payload.inputs_hash == inputs_hash)
        )
        return existing.scalar_one(), False

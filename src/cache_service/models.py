from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Transformation(Base):
    __tablename__ = "transformations"

    input_text: Mapped[str] = mapped_column(Text, primary_key=True)
    output_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Payload(Base):
    __tablename__ = "payloads"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    inputs_hash: Mapped[str] = mapped_column(String(64), unique=True)
    output: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

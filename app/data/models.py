import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum,
    Index,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.services.models import CurrencyVO, PaymentStatusVO

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _pg_enum(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


class PaymentDAO(Base):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("idempotency_key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[CurrencyVO] = mapped_column(_pg_enum(CurrencyVO, "currency"))
    description: Mapped[str] = mapped_column(String(1024))
    extra_data: Mapped[dict[str, Any]] = mapped_column("extra_data", JSONB, server_default="{}")
    status: Mapped[PaymentStatusVO] = mapped_column(
        _pg_enum(PaymentStatusVO, "payment_status"), default=PaymentStatusVO.PENDING
    )
    idempotency_key: Mapped[str] = mapped_column(String(255))
    request_hash: Mapped[str] = mapped_column(String(64))
    webhook_url: Mapped[str] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    webhook_delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutboxEventDAO(Base):
    __tablename__ = "outbox"
    __table_args__ = (
        Index(
            "ix_outbox_unpublished",
            "created_at",
            postgresql_where=text("published_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    aggregate_id: Mapped[uuid.UUID]
    event_type: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)

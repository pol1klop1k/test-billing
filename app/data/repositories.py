import uuid
from typing import Any, Self

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.data.db import session_factory
from app.data.mappers import outbox_event_to_do, payment_to_do
from app.data.models import OutboxEventDAO, PaymentDAO
from app.services.models import NewPaymentDO, OutboxEventDO, PaymentDO, PaymentStatusVO
from app.services.repositories import UnitOfWork


class SQLAlchemyPaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self, payment_id: uuid.UUID, data: NewPaymentDO, idempotency_key: str, request_hash: str
    ) -> PaymentDO | None:
        payment = await self._session.scalar(
            insert(PaymentDAO)
            .values(
                id=payment_id,
                amount=data.amount,
                currency=data.currency,
                description=data.description,
                extra_data=data.metadata,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                webhook_url=data.webhook_url,
            )
            .on_conflict_do_nothing(index_elements=[PaymentDAO.idempotency_key])
            .returning(PaymentDAO)
        )
        return payment_to_do(payment) if payment is not None else None

    async def get(self, payment_id: uuid.UUID, *, for_update: bool = False) -> PaymentDO | None:
        payment = await self._session.get(PaymentDAO, payment_id, with_for_update=for_update)
        return payment_to_do(payment) if payment is not None else None

    async def get_by_idempotency_key(self, idempotency_key: str) -> PaymentDO:
        payment = await self._session.scalar(
            select(PaymentDAO).where(PaymentDAO.idempotency_key == idempotency_key)
        )
        if payment is None:
            raise LookupError(f"Payment with idempotency key {idempotency_key!r} not found")
        return payment_to_do(payment)

    async def set_status(self, payment_id: uuid.UUID, status: PaymentStatusVO) -> PaymentDO:
        payment = await self._session.scalar(
            update(PaymentDAO)
            .where(PaymentDAO.id == payment_id)
            .values(status=status, processed_at=func.now())
            .returning(PaymentDAO)
            .execution_options(populate_existing=True)
        )
        return payment_to_do(payment)

    async def mark_webhook_delivered(self, payment_id: uuid.UUID) -> None:
        await self._session.execute(
            update(PaymentDAO)
            .where(PaymentDAO.id == payment_id)
            .values(webhook_delivered_at=func.now())
        )


class SqlAlchemyOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, aggregate_id: uuid.UUID, event_type: str, payload: dict[str, Any]) -> None:
        self._session.add(
            OutboxEventDAO(aggregate_id=aggregate_id, event_type=event_type, payload=payload)
        )

    async def get_unpublished(self, limit: int) -> list[OutboxEventDO]:
        events = await self._session.scalars(
            select(OutboxEventDAO)
            .where(OutboxEventDAO.published_at.is_(None))
            .order_by(OutboxEventDAO.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return [outbox_event_to_do(event) for event in events]

    async def mark_published(self, event_id: uuid.UUID) -> None:
        await self._session.execute(
            update(OutboxEventDAO)
            .where(OutboxEventDAO.id == event_id)
            .values(published_at=func.now())
        )

    async def mark_failed(self, event_id: uuid.UUID, error: str) -> None:
        await self._session.execute(
            update(OutboxEventDAO)
            .where(OutboxEventDAO.id == event_id)
            .values(attempts=OutboxEventDAO.attempts + 1, last_error=error)
        )


class SqlAlchemyUnitOfWork:
    payments: SQLAlchemyPaymentRepository
    outbox: SqlAlchemyOutboxRepository

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        if self._session is not None:
            raise RuntimeError("Unit of work is already active")
        self._session = self._factory()
        self.payments = SQLAlchemyPaymentRepository(self._session)
        self.outbox = SqlAlchemyOutboxRepository(self._session)
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        session, self._session = self._session, None
        await session.close()

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of work is not active")
        await self._session.commit()


def get_uow() -> UnitOfWork:
    return SqlAlchemyUnitOfWork(session_factory)

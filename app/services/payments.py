import hashlib
import json
import uuid

from app.messaging.models import PaymentCreatedEventDTO
from app.services.models import NewPaymentDO, PaymentDO
from app.services.repositories import UnitOfWork

PAYMENT_CREATED_EVENT = "payment.created"


class IdempotencyConflictError(Exception): ...


def _request_hash(data: NewPaymentDO) -> str:
    canonical = json.dumps(data.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


async def create_payment(uow: UnitOfWork, data: NewPaymentDO, idempotency_key: str) -> PaymentDO:
    request_hash = _request_hash(data)
    payment_id = uuid.uuid4()

    async with uow:
        payment = await uow.payments.add(payment_id, data, idempotency_key, request_hash)
        if payment is not None:
            await uow.outbox.add(
                payment_id,
                PAYMENT_CREATED_EVENT,
                PaymentCreatedEventDTO(payment_id=payment_id).model_dump(mode="json"),
            )
        else:
            payment = await uow.payments.get_by_idempotency_key(idempotency_key)
            if payment.request_hash != request_hash:
                raise IdempotencyConflictError
        await uow.commit()

    return payment


async def get_payment(uow: UnitOfWork, payment_id: uuid.UUID) -> PaymentDO | None:
    async with uow:
        return await uow.payments.get(payment_id)

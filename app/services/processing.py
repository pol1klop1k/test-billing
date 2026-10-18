import logging
import uuid

from app.services import gateway
from app.services.models import PaymentStatusVO, WebhookPayloadDTO
from app.services.repositories import UnitOfWork
from app.services.webhooks import send_webhook

logger = logging.getLogger(__name__)


class PaymentNotFoundError(Exception):
    pass


async def process_payment(uow: UnitOfWork, payment_id: uuid.UUID, event_id: uuid.UUID) -> None:
    async with uow:
        payment = await uow.payments.get(payment_id, for_update=True)
        if payment is None:
            raise PaymentNotFoundError(payment_id)

        if payment.status is PaymentStatusVO.PENDING:
            status = await gateway.process_payment(idempotency_key=str(payment.id))
            payment = await uow.payments.set_status(payment_id, status)
            logger.info("Payment %s processed: %s", payment_id, payment.status)
        else:
            logger.warning("Payment %s was already processed: %s", payment_id, payment.status)
        await uow.commit()

    if payment.webhook_delivered_at is not None:
        logger.warning("Webhook for payment %s already delivered, skipping", payment_id)
        return

    await send_webhook(
        payment.webhook_url,
        WebhookPayloadDTO(
            event_id=event_id,
            payment_id=payment.id,
            status=payment.status,
            amount=payment.amount,
            currency=payment.currency,
            processed_at=payment.processed_at,
        ),
    )
    async with uow:
        await uow.payments.mark_webhook_delivered(payment_id)
        await uow.commit()
    logger.info("Webhook for payment %s delivered to %s", payment_id, payment.webhook_url)

from app.data.models import OutboxEventDAO, PaymentDAO
from app.services.models import OutboxEventDO, PaymentDO


def payment_to_do(payment: PaymentDAO) -> PaymentDO:
    return PaymentDO(
        id=payment.id,
        amount=payment.amount,
        currency=payment.currency,
        description=payment.description,
        metadata=payment.extra_data,
        status=payment.status,
        idempotency_key=payment.idempotency_key,
        request_hash=payment.request_hash,
        webhook_url=payment.webhook_url,
        created_at=payment.created_at,
        processed_at=payment.processed_at,
        webhook_delivered_at=payment.webhook_delivered_at,
    )


def outbox_event_to_do(event: OutboxEventDAO) -> OutboxEventDO:
    return OutboxEventDO(
        id=event.id,
        aggregate_id=event.aggregate_id,
        event_type=event.event_type,
        payload=event.payload,
        created_at=event.created_at,
        published_at=event.published_at,
        attempts=event.attempts,
        last_error=event.last_error,
    )

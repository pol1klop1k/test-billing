import logging
import uuid
from typing import Annotated

from faststream import AckPolicy, Depends, FastStream
from faststream.rabbit.annotations import RabbitMessage
from pydantic import ValidationError

from app.config import get_settings
from app.data.db import engine
from app.data.repositories import get_uow
from app.messaging.broker import broker
from app.messaging.models import PaymentCreatedEventDTO
from app.messaging.topology import (
    Exchanges,
    Headers,
    Queues,
    declare_topology,
    retry_routing_key,
)
from app.services.processing import PaymentNotFoundError, process_payment
from app.services.repositories import UnitOfWork

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("consumer")

app = FastStream(broker)


@app.on_startup
async def setup_topology() -> None:
    await broker.connect()
    await declare_topology(broker)


@app.after_shutdown
async def dispose_engine() -> None:
    await engine.dispose()


@broker.subscriber(Queues.PAYMENTS_NEW, Exchanges.PAYMENTS, ack_policy=AckPolicy.MANUAL)
async def handle_payment_created(
    msg: RabbitMessage,
    uow: Annotated[UnitOfWork, Depends(get_uow, cast=False)],
) -> None:
    try:
        event = PaymentCreatedEventDTO.model_validate_json(msg.body)
    except ValidationError:
        logger.exception("Invalid message %s, rejecting to DLQ", msg.message_id)
        await msg.reject(requeue=False)
        return

    attempt = int(msg.headers.get(Headers.ATTEMPT, 1))
    event_id = _event_id(msg.message_id, event.payment_id)

    try:
        await process_payment(uow, event.payment_id, event_id)
    except PaymentNotFoundError:
        logger.error("Payment %s not found, rejecting to DLQ", event.payment_id)
        await msg.reject(requeue=False)
        return
    except Exception as exc:
        await _schedule_retry(msg, attempt, exc)
        return

    await msg.ack()


async def _schedule_retry(msg: RabbitMessage, attempt: int, exc: Exception) -> None:
    max_attempts = get_settings().max_attempts
    error = f"{type(exc).__name__}: {exc}"[:1000]
    headers = {**msg.headers, Headers.LAST_ERROR: error}

    if attempt < max_attempts:
        logger.warning(
            "Attempt %s/%s for message %s failed: %s. Scheduling retry",
            attempt,
            max_attempts,
            msg.message_id,
            error,
        )
        exchange, routing_key = Exchanges.PAYMENTS_RETRY, retry_routing_key(attempt)
        headers[Headers.ATTEMPT] = attempt + 1
    else:
        logger.error(
            "Attempt %s/%s for message %s failed: %s. Moving to DLQ",
            attempt,
            max_attempts,
            msg.message_id,
            error,
        )
        exchange, routing_key = Exchanges.PAYMENTS_DLX, ""

    try:
        await broker.publish(
            msg.body,
            exchange=exchange,
            routing_key=routing_key,
            headers=headers,
            message_id=msg.message_id,
            content_type=msg.content_type,
            persist=True,
        )
    except Exception:
        logger.exception("Failed to republish message %s, requeueing", msg.message_id)
        await msg.nack(requeue=True)
        return

    await msg.ack()


def _event_id(message_id: str | None, payment_id: uuid.UUID) -> uuid.UUID:
    try:
        return uuid.UUID(message_id)
    except (TypeError, ValueError):
        return payment_id

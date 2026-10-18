import asyncio
import contextlib
import logging
import signal

from app.config import get_settings
from app.data.db import engine
from app.data.repositories import get_uow
from app.messaging.broker import broker
from app.messaging.topology import Exchanges, RoutingKeys, declare_topology
from app.services.repositories import UnitOfWork

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("outbox")


async def publish_batch(uow: UnitOfWork, batch_size: int) -> int:
    published = 0
    async with uow:
        for event in await uow.outbox.get_unpublished(batch_size):
            try:
                await broker.publish(
                    event.payload,
                    exchange=Exchanges.PAYMENTS,
                    routing_key=RoutingKeys.PAYMENTS_NEW,
                    message_id=str(event.id),
                    message_type=event.event_type,
                    persist=True,
                )
            except Exception as exc:
                logger.warning("Failed to publish outbox event %s: %s", event.id, exc)
                await uow.outbox.mark_failed(event.id, f"{type(exc).__name__}: {exc}"[:1000])
                break
            await uow.outbox.mark_published(event.id)
            published += 1
        await uow.commit()
    return published


async def run() -> None:
    settings = get_settings()
    uow = get_uow()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    await broker.connect()
    await declare_topology(broker)
    logger.info("Outbox started")

    try:
        while not stop.is_set():
            try:
                published = await publish_batch(uow, settings.outbox_batch_size)
            except Exception:
                logger.exception("Outbox iteration failed")
                published = 0
            if published:
                logger.info("Published %s outbox events", published)
            if published < settings.outbox_batch_size:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=settings.outbox_poll_interval)
    finally:
        await broker.stop()
        await engine.dispose()
        logger.info("Outbox stopped")


if __name__ == "__main__":
    asyncio.run(run())

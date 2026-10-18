from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from app.config import get_settings
from app.utils.frozennamespace import FrozenNamespace


class RoutingKeys(FrozenNamespace):
    PAYMENTS_NEW = "payments.new"


class Headers(FrozenNamespace):
    ATTEMPT = "x-attempt"
    LAST_ERROR = "x-last-error"


class Exchanges(FrozenNamespace):
    PAYMENTS = RabbitExchange("payments", type=ExchangeType.DIRECT, durable=True)
    PAYMENTS_RETRY = RabbitExchange("payments.retry", type=ExchangeType.DIRECT, durable=True)
    PAYMENTS_DLX = RabbitExchange("payments.dlx", type=ExchangeType.FANOUT, durable=True)


class Queues(FrozenNamespace):
    PAYMENTS_NEW = RabbitQueue(
        "payments.new",
        durable=True,
        routing_key=RoutingKeys.PAYMENTS_NEW,
        arguments={"x-dead-letter-exchange": Exchanges.PAYMENTS_DLX.name},
    )
    PAYMENTS_NEW_DLQ = RabbitQueue("payments.new.dlq", durable=True)


def retry_queues() -> list[RabbitQueue]:
    settings = get_settings()
    return [
        RabbitQueue(
            retry_routing_key(attempt),
            durable=True,
            routing_key=retry_routing_key(attempt),
            arguments={
                "x-message-ttl": settings.retry_base_delay_ms * 2 ** (attempt - 1),
                "x-dead-letter-exchange": Exchanges.PAYMENTS.name,
                "x-dead-letter-routing-key": RoutingKeys.PAYMENTS_NEW,
            },
        )
        for attempt in range(1, settings.max_attempts)
    ]


def retry_routing_key(attempt: int) -> str:
    return f"payments.new.retry.{attempt}"


async def declare_topology(broker: RabbitBroker) -> None:
    exchanges = {}
    for exchange in (Exchanges.PAYMENTS, Exchanges.PAYMENTS_RETRY, Exchanges.PAYMENTS_DLX):
        exchanges[exchange.name] = await broker.declare_exchange(exchange)

    bindings = [
        (Queues.PAYMENTS_NEW, Exchanges.PAYMENTS),
        (Queues.PAYMENTS_NEW_DLQ, Exchanges.PAYMENTS_DLX),
        *((queue, Exchanges.PAYMENTS_RETRY) for queue in retry_queues()),
    ]
    for queue, exchange in bindings:
        declared = await broker.declare_queue(queue)
        await declared.bind(exchanges[exchange.name], routing_key=queue.routing_key)

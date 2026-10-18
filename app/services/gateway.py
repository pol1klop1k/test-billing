import asyncio
import random

from app.config import get_settings
from app.services.models import PaymentStatusVO

_results: dict[str, PaymentStatusVO] = {}


async def process_payment(idempotency_key: str) -> PaymentStatusVO:
    if (status := _results.get(idempotency_key)) is not None:
        return status

    settings = get_settings()
    await asyncio.sleep(random.uniform(settings.gateway_min_delay, settings.gateway_max_delay))
    if random.random() < settings.gateway_success_rate:
        status = PaymentStatusVO.SUCCEEDED
    else:
        status = PaymentStatusVO.FAILED
    _results[idempotency_key] = status
    return status

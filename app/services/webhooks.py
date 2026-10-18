import httpx

from app.config import get_settings
from app.services.models import WebhookPayloadDTO


class WebhookDeliveryError(Exception):
    pass


async def send_webhook(url: str, payload: WebhookPayloadDTO) -> None:
    try:
        async with httpx.AsyncClient(timeout=get_settings().webhook_timeout) as client:
            response = await client.post(
                url,
                content=payload.model_dump_json(),
                headers={"Content-Type": "application/json", "X-Event-Id": str(payload.event_id)},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise WebhookDeliveryError(f"{type(exc).__name__}: {exc}") from exc

import logging
import os
import random
from typing import Any

from fastapi import FastAPI, Request, Response, status

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("webhook_receiver")

FAIL_RATE = float(os.getenv("FAIL_RATE", "0"))

app = FastAPI(title="Webhook receiver (mock)")
received: list[dict[str, Any]] = []


@app.post("/webhook")
async def webhook(request: Request) -> Response:
    payload = await request.json()
    event_id = request.headers.get("X-Event-Id")
    if random.random() < FAIL_RATE:
        logger.warning("Simulated failure for event %s", event_id)
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    logger.info("Received event %s: %s", event_id, payload)
    received.append({"event_id": event_id, "payload": payload})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/webhook/fail")
async def webhook_fail(request: Request) -> Response:
    logger.warning("Always-failing endpoint hit, event %s", request.headers.get("X-Event-Id"))
    return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@app.get("/webhooks")
async def list_webhooks() -> list[dict[str, Any]]:
    return received

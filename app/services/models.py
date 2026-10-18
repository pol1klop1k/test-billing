import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class CurrencyVO(enum.StrEnum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class PaymentStatusVO(enum.StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class NewPaymentDO(BaseModel):
    model_config = ConfigDict(frozen=True)

    amount: Decimal
    currency: CurrencyVO
    description: str
    metadata: dict[str, Any]
    webhook_url: str


class PaymentDO(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    amount: Decimal
    currency: CurrencyVO
    description: str
    metadata: dict[str, Any]
    status: PaymentStatusVO
    idempotency_key: str
    request_hash: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None
    webhook_delivered_at: datetime | None


class OutboxEventDO(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    aggregate_id: uuid.UUID
    event_type: str
    payload: dict[str, Any]
    created_at: datetime
    published_at: datetime | None
    attempts: int
    last_error: str | None


class WebhookPayloadDTO(BaseModel):
    event_id: uuid.UUID
    payment_id: uuid.UUID
    status: PaymentStatusVO
    amount: Decimal
    currency: CurrencyVO
    processed_at: datetime | None

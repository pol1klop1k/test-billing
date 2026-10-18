import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.services.models import CurrencyVO, NewPaymentDO, PaymentDO, PaymentStatusVO

Amount = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)]


class PaymentCreateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Amount
    currency: CurrencyVO
    description: str = Field(min_length=1, max_length=1024)
    metadata: dict[str, Any] = Field(default_factory=dict)
    webhook_url: HttpUrl

    def to_command(self) -> NewPaymentDO:
        return NewPaymentDO(
            amount=self.amount,
            currency=self.currency,
            description=self.description,
            metadata=self.metadata,
            webhook_url=str(self.webhook_url),
        )


class PaymentAcceptedDTO(BaseModel):
    payment_id: uuid.UUID
    status: PaymentStatusVO
    created_at: datetime

    @classmethod
    def from_domain(cls, payment: PaymentDO) -> Self:
        return cls(payment_id=payment.id, status=payment.status, created_at=payment.created_at)


class PaymentReadDTO(BaseModel):
    payment_id: uuid.UUID
    amount: Decimal
    currency: CurrencyVO
    description: str
    metadata: dict[str, Any]
    status: PaymentStatusVO
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None
    webhook_delivered_at: datetime | None

    @classmethod
    def from_domain(cls, payment: PaymentDO) -> Self:
        return cls(
            payment_id=payment.id,
            amount=payment.amount,
            currency=payment.currency,
            description=payment.description,
            metadata=payment.metadata,
            status=payment.status,
            idempotency_key=payment.idempotency_key,
            webhook_url=payment.webhook_url,
            created_at=payment.created_at,
            processed_at=payment.processed_at,
            webhook_delivered_at=payment.webhook_delivered_at,
        )

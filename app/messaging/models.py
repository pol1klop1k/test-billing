import uuid

from pydantic import BaseModel


class PaymentCreatedEventDTO(BaseModel):
    payment_id: uuid.UUID

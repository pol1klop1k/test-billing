import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import IdempotencyKey, UnitOfWorkDep, verify_api_key
from app.api.models import PaymentAcceptedDTO, PaymentCreateDTO, PaymentReadDTO
from app.services import payments as payment_service

router = APIRouter(
    prefix="/api/v1/payments", tags=["payments"], dependencies=[Depends(verify_api_key)]
)


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=PaymentAcceptedDTO)
async def create_payment(
    data: PaymentCreateDTO, idempotency_key: IdempotencyKey, uow: UnitOfWorkDep
) -> PaymentAcceptedDTO:
    try:
        payment = await payment_service.create_payment(uow, data.to_command(), idempotency_key)
    except payment_service.IdempotencyConflictError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Idempotency-Key already used with a different request body",
        )
    return PaymentAcceptedDTO.from_domain(payment)


@router.get("/{payment_id}", response_model=PaymentReadDTO)
async def get_payment(payment_id: uuid.UUID, uow: UnitOfWorkDep) -> PaymentReadDTO:
    payment = await payment_service.get_payment(uow, payment_id)
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")
    return PaymentReadDTO.from_domain(payment)

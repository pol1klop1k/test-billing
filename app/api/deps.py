import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import get_settings
from app.data.repositories import get_uow
from app.services.repositories import UnitOfWork

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Annotated[str | None, Depends(api_key_header)]) -> None:
    if api_key is None or not secrets.compare_digest(api_key, get_settings().api_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key")


UnitOfWorkDep = Annotated[UnitOfWork, Depends(get_uow)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]

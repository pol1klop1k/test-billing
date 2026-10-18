from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://billing:billing@localhost:5432/billing"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    api_key: str = Field(min_length=1)

    outbox_poll_interval: float = 1.0
    outbox_batch_size: int = 100

    consumer_prefetch_count: int = 10
    max_attempts: int = Field(default=3, ge=1)
    retry_base_delay_ms: int = Field(default=1000, ge=1)
    webhook_timeout: float = 5.0

    gateway_min_delay: float = 2.0
    gateway_max_delay: float = 5.0
    gateway_success_rate: float = Field(default=0.9, ge=0, le=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()

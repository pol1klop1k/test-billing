# Асинхронный сервис процессинга платежей

Сервис принимает платёж (`202 Accepted`), асинхронно проводит его через эмулятор платёжного шлюза и уведомляет клиента о результате через webhook.

**Стек:** FastAPI + Pydantic v2, SQLAlchemy 2 (async, asyncpg), PostgreSQL, RabbitMQ (FastStream), Alembic, Docker Compose, uv, ruff.



Сервисы `docker-compose.yml`:

| Сервис | Назначение                                                |
|---|-----------------------------------------------------------|
| `postgres` | БД (таблицы `payments`, `outbox`)                         |
| `rabbitmq` | брокер, UI: http://localhost:15672 (guest/guest)          |
| `migrate` | одноразовый `alembic upgrade head`                        |
| `api` | HTTP API, http://localhost:8000/docs                      |
| `outbox` | публикация событий из `outbox` в RabbitMQ                 |
| `consumer` | обработчик очереди `payments.new`                         |
| `webhook-receiver` | mock-сервис уведомлений по webhook, http://localhost:8001 |

Структура кода:

```
app/
  api/            # REST
  services/       # бизнес-логика
  messaging/      # RabbitMQ
  data/           # БД
migrations/       # Alembic
webhook_receiver/ # mock-сервис уведомлений
```

## Запуск

```bash
cp .env.example .env      # при необходимости поменять API_KEY и порты
docker compose up --build -d
```

Если порты 8000/8001/15672 на хосте заняты - переопределите `API_PORT`, `WEBHOOK_RECEIVER_PORT`, `RABBITMQ_UI_PORT` в `.env`.
Postgres и AMQP наружу не публикуются.

## API

Все эндпоинты требуют заголовок `X-API-Key` (значение `API_KEY` из `.env`), иначе `401`.

### Создание платежа

```bash
curl -i -X POST http://localhost:8000/api/v1/payments \
  -H "X-API-Key: change-me" \
  -H "Idempotency-Key: order-1" \
  -H "Content-Type: application/json" \
  -d '{
        "amount": "100.50",
        "currency": "RUB",
        "description": "Order #1",
        "metadata": {"order_id": 1},
        "webhook_url": "http://webhook-receiver:8001/webhook"
      }'
```

```http
HTTP/1.1 202 Accepted

{"payment_id": "7b91b3c0-5d2e-4f8a-9c1b-2e6f0a4d8c37", "status": "pending", "created_at": "2026-10-14T20:29:50.172776Z"}
```


- Без `Idempotency-Key` или с невалидным телом ручка возвращает `422`.
- Повторный запрос с тем же ключом идемпотентности и тем же телом возвращает уже созданный платёж (`202`, тот же `payment_id`, новое событие не создаётся). Тот же ключ с другим телом - `409 Conflict`.

### Получение платежа

```bash
curl http://localhost:8000/api/v1/payments/<payment_id> -H "X-API-Key: change-me"
```

```json
{
  "payment_id": "7b91b3c0-5d2e-4f8a-9c1b-2e6f0a4d8c37",
  "amount": "100.50",
  "currency": "RUB",
  "description": "Order #1",
  "metadata": {"order_id": 1},
  "status": "succeeded",
  "idempotency_key": "order-1",
  "webhook_url": "http://webhook-receiver:8001/webhook",
  "created_at": "2026-10-14T20:29:50.172776Z",
  "processed_at": "2026-10-14T20:29:54.116099Z",
  "webhook_delivered_at": "2026-10-14T20:29:54.201111Z"
}
```

Несуществующий платёж - `404`.

### Webhook

`POST` на `webhook_url`:

```json
{
  "event_id": "3c62d5f8-a1e4-4b7d-8f02-6d9e1c5b7a43",
  "payment_id": "7b91b3c0-5d2e-4f8a-9c1b-2e6f0a4d8c37",
  "status": "succeeded",
  "amount": "100.50",
  "currency": "RUB",
  "processed_at": "2026-10-14T20:29:54.116099Z"
}
```

Любой ответ, кроме `2xx`, а также таймаут/сетевая ошибка считаются неудачной доставкой.

## Проверка сценариев

**Успешный поток.** Создайте платёж с `webhook_url=http://webhook-receiver:8001/webhook`, через ~5с `GET` покажет итоговый статус, а уведомление появится в `curl http://localhost:8001/webhooks`.

**Retry и DLQ.** Укажите `webhook_url=http://webhook-receiver:8001/webhook/fail` (всегда отвечает 500):

```bash
docker compose logs -f consumer
# Attempt 1/3 ... failed ... Scheduling retry
# Attempt 2/3 ... failed ... Scheduling retry
# Attempt 3/3 ... failed ... Moving to DLQ
docker compose exec rabbitmq rabbitmqctl list_queues name messages
# payments.new.dlq  1
```

В DLQ сообщение лежит с заголовками `x-attempt` и `x-last-error`. Нестабильный приёмник можно эмулировать через `WEBHOOK_RECEIVER_FAIL_RATE=0.5`.

**Гарантия публикации (outbox).**

```bash
docker compose stop rabbitmq
# создать платёж, API отвечает 202, событие остаётся в outbox (published_at IS NULL)
docker compose start rabbitmq
# relay публикует событие, платёж обрабатывается
```

## Переменные окружения

| Переменная | По умолчанию  | Описание                                           |
|---|---------------|----------------------------------------------------|
| `API_KEY` | -             | статический ключ для `X-API-Key`                   |
| `DATABASE_URL` | -             | DSN `postgresql+asyncpg://...`                     |
| `RABBITMQ_URL` | -             | DSN `amqp://...`                                   |
| `OUTBOX_POLL_INTERVAL` | `1.0`         | период опроса outbox, с                            |
| `OUTBOX_BATCH_SIZE` | `100`         | размер пачки outbox                                |
| `CONSUMER_PREFETCH_COUNT` | `10`          | сколько сообщений consumer обрабатывает параллельно |
| `MAX_ATTEMPTS` | `3`           | всего попыток обработки до DLQ                     |
| `RETRY_BASE_DELAY_MS` | `1000`        | задержка перед повтором N: `base * 2^(N-1)`        |
| `WEBHOOK_TIMEOUT` | `5.0`         | таймаут webhook, с                                 |
| `GATEWAY_MIN_DELAY` / `GATEWAY_MAX_DELAY` | `2.0` / `5.0` | время обработки шлюзом, с                          |
| `GATEWAY_SUCCESS_RATE` | `0.9`         | доля успешных платежей                             |
| `WEBHOOK_RECEIVER_FAIL_RATE` | `0.0`         | доля ответов 500 у mock-приёмника                  |

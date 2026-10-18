FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY webhook_receiver ./webhook_receiver

RUN useradd --create-home --uid 1000 app
USER app

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

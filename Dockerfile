# syntax=docker/dockerfile:1

FROM node:22-alpine AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS runtime
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY --from=ui /ui/dist ./frontend/dist

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/v1/workflows', timeout=3).status == 200 else 1)"

# --limit-concurrency: a connection flood gets 503 instead of eating the host.
# --ws-max-size: the browser never sends anything on the socket, so no inbound frame needs 16 MiB.
# --no-access-log: the healthcheck fills it and it prints sessionId out of query strings; the requests that matter are logged by the app itself.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--limit-concurrency", "200", "--ws-max-size", "1024", "--no-access-log"]

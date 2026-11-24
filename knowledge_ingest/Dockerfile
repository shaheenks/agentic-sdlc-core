# Build context: the repository root (uv workspace): docker build -f knowledge_ingest/Dockerfile .
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.16 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY . .
RUN uv sync --frozen --no-dev --no-editable --package sdlc-knowledge-ingest

FROM python:3.12-slim
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH
USER nobody
CMD ["sdlc-knowledge-ingest"]

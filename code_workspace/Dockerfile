# Build context: the repository root (uv workspace): docker build -f code_workspace/Dockerfile .
# The platform's default Code Workspace image (DEC-0015): git, Python 3.12 and Node.js for the repositories' own
# build and test commands, run as an unprivileged user with a scratch home.
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.16 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY . .
RUN uv sync --frozen --no-dev --no-editable --package sdlc-code-workspace

FROM python:3.12-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates nodejs npm \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/.venv /app/.venv
# The job's own code runs from /app/.venv; the repository's commands get the system Python on PATH after it.
ENV PATH=/app/.venv/bin:$PATH HOME=/tmp PYTHONUNBUFFERED=1
USER nobody
CMD ["sdlc-code-workspace"]

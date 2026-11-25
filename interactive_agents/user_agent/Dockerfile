# Local Docker Compose only: the runtime application served in Agent Runtime's request shape (python -m
# user_agent). In Google Cloud it runs on Agent Runtime instead (deploy.py).
# Build context: the repository root (uv workspace): docker build -f interactive_agents/user_agent/Dockerfile .
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.16 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY . .
RUN uv sync --frozen --no-dev --no-editable --package sdlc-user-agent

FROM python:3.12-slim
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH PORT=8085
USER nobody
EXPOSE 8085
CMD ["python", "-m", "user_agent"]

# Build context: repo root (uv workspace). See docker-compose.yml (profile "ingest").
# One image, two jobs, run on demand:
#   docker compose run --rm ingest run --all            (as sdlc_ingest)
#   docker compose run --rm migrate                     (sdlc-db migrate, as sdlc_owner)
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.16 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./
COPY libs/sdlc_agent/pyproject.toml libs/sdlc_agent/
COPY libs/sdlc_auth/pyproject.toml libs/sdlc_auth/
COPY libs/sdlc_config/pyproject.toml libs/sdlc_config/
COPY libs/sdlc_db/pyproject.toml libs/sdlc_db/
COPY libs/sdlc_policy/pyproject.toml libs/sdlc_policy/
COPY libs/sdlc_web/pyproject.toml libs/sdlc_web/
COPY ingest/bootstrap/pyproject.toml ingest/bootstrap/
COPY mcp_servers/bootstrap/pyproject.toml mcp_servers/bootstrap/
COPY agents/bootstrap/pyproject.toml agents/bootstrap/
RUN uv sync --frozen --no-dev --package sdlc-ingest --no-install-workspace

COPY libs/sdlc_config libs/sdlc_config
COPY libs/sdlc_db libs/sdlc_db
COPY ingest/bootstrap ingest/bootstrap
RUN uv sync --frozen --no-dev --package sdlc-ingest

# Migrations are baked in (versioned with the code). docker compose bind-mounts ./config,
# ./skills (config validation checks skill files) and ./samples; baked-in copies are for
# standalone runs.
COPY db/migrations db/migrations
COPY config config
COPY skills skills

ENV PATH=/app/.venv/bin:$PATH \
    SDLC_CONFIG_DIR=/app/config \
    SDLC_ENV=local \
    HOME=/tmp
USER nobody
ENTRYPOINT ["sdlc-ingest"]
CMD ["run", "--all"]

# Build context: repo root (uv workspace). See docker-compose.yml.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.16 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

# Dependencies first (cached layer): workspace manifests + lockfile only.
COPY pyproject.toml uv.lock ./
COPY mcp_servers/bootstrap/pyproject.toml mcp_servers/bootstrap/
COPY agents/bootstrap/pyproject.toml agents/bootstrap/
RUN uv sync --frozen --no-dev --package sdlc-mcp-bootstrap --no-install-workspace

COPY mcp_servers/bootstrap mcp_servers/bootstrap
RUN uv sync --frozen --no-dev --package sdlc-mcp-bootstrap

# Baked-in copy for standalone runs; docker compose bind-mounts ./skills over it.
COPY skills skills

ENV PATH=/app/.venv/bin:$PATH \
    SDLC_SKILLS_DIR=/app/skills/bootstrap \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8080
USER nobody
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz')"
CMD ["sdlc-mcp-bootstrap"]

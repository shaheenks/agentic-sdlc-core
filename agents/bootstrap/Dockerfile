# Build context: repo root (uv workspace). See docker-compose.yml.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.16 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./
COPY libs/sdlc_auth/pyproject.toml libs/sdlc_auth/
COPY libs/sdlc_config/pyproject.toml libs/sdlc_config/
COPY mcp_servers/bootstrap/pyproject.toml mcp_servers/bootstrap/
COPY agents/bootstrap/pyproject.toml agents/bootstrap/
RUN uv sync --frozen --no-dev --package sdlc-agent-bootstrap --no-install-workspace

# adk web serves every agent package under /app/agents; this image ships only bootstrap.
COPY agents/bootstrap agents/bootstrap

ENV PATH=/app/.venv/bin:$PATH \
    SDLC_MCP_URL=http://mcp-bootstrap:8080/mcp \
    HOME=/tmp
USER nobody
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/list-apps')"
CMD ["adk", "web", "--host", "0.0.0.0", "--port", "8000", "/app/agents"]

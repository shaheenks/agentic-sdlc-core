# Build context: repo root (uv workspace). See docker-compose.yml.
# Serves the agents with sdlc-agent-web (ADK web app + Entra user binding), reached only
# through oauth2-proxy.
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
RUN uv sync --frozen --no-dev --package sdlc-web --package sdlc-agent-bootstrap --no-install-workspace

COPY libs/sdlc_agent libs/sdlc_agent
COPY libs/sdlc_auth libs/sdlc_auth
COPY libs/sdlc_web libs/sdlc_web
RUN uv sync --frozen --no-dev --package sdlc-web --package sdlc-agent-bootstrap

# The web app serves every agent package under /app/agents; this image ships only bootstrap.
COPY agents/bootstrap agents/bootstrap

ENV PATH=/app/.venv/bin:$PATH \
    SDLC_AGENTS_DIR=/app/agents \
    SDLC_MCP_URL=http://mcp-bootstrap:8080/mcp \
    HOST=0.0.0.0 \
    PORT=8000 \
    HOME=/tmp
# Conversation store (SDLC_SESSION_SERVICE_URI=sqlite:////data/sessions.db): a named volume
# mounted here inherits this ownership on first use.
RUN mkdir -p /data && chown nobody /data
USER nobody
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["sdlc-agent-web"]

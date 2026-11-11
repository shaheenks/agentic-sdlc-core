"""docker-compose.yml keeps its trace claims: least privilege, configurable hosts and tracing.

CH-0006.

Offline: parses the file only (no Docker, no .env).
"""

import re
from pathlib import Path

import pytest
import yaml

COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.yml"

# Services that may hold database settings or credentials (NFR-SEC-010).
DB_SERVICES = {"postgres", "core-mcp", "migrate", "ingest"}
DB_VAR = re.compile(r"^(POSTGRES_|PG|DATABASE_URL$)")


@pytest.fixture(scope="module")
def services() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]


def env(service: dict) -> dict:
    return service.get("environment") or {}


def test_agent_and_chat_app_get_no_env_file_and_no_db_settings(services):
    for name in ("user-agent", "ui-copilotkit"):
        assert "env_file" not in services[name], name
        assert not [k for k in env(services[name]) if DB_VAR.match(k)], name


def test_only_db_services_get_db_settings(services):
    with_db = {name for name, s in services.items() if any(DB_VAR.match(k) for k in env(s))}
    assert with_db <= DB_SERVICES
    assert {"core-mcp", "migrate", "ingest"} <= with_db


def test_public_hosts_come_from_variables(services):
    """NFR-PORT-002: the tunnel hosts are configuration; only the local proxy names localhost."""
    assert "${SDLC_MCP_HOST" in env(services["core-mcp"])["MCP_PUBLIC_URL"]
    public = env(services["oauth2-proxy-public"])
    assert "${SDLC_APP_HOST" in public["OAUTH2_PROXY_REDIRECT_URL"]
    assert "${SDLC_APP_HOST" in public["OAUTH2_PROXY_WHITELIST_DOMAINS"]
    for name, service in services.items():
        if name == "oauth2-proxy":  # the localhost sign-in path itself
            continue
        for key, value in env(service).items():
            if isinstance(value, str) and "localhost" in value:
                # only as a default inside ${VAR:-...}
                assert re.search(r"\$\{[A-Z_]+:?-[^}]*localhost", value), (name, key)


def test_mcp_and_agent_export_traces(services):
    """NFR-OBS-001: tracing is wired for both; off unless the endpoint is set."""
    for name in ("core-mcp", "user-agent"):
        assert "OTEL_EXPORTER_OTLP_ENDPOINT" in env(services[name]), name
        assert env(services[name]).get("OTEL_SERVICE_NAME"), name

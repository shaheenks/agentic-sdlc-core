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
DB_SERVICES = {"postgres", "core-mcp", "core-mcp-gcp", "migrate", "ingest"}
# Local sign-in paths themselves (each stack's localhost proxy).
LOCAL_SIGN_IN = {"oauth2-proxy", "oauth2-proxy-gcp"}
DB_VAR = re.compile(r"^(POSTGRES_|PG|DATABASE_URL$)")


@pytest.fixture(scope="module")
def services() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]


def env(service: dict) -> dict:
    return service.get("environment") or {}


def test_agent_and_chat_app_get_no_env_file_and_no_db_settings(services):
    for name in ("user-agent", "user-agent-gcp", "ui-copilotkit"):
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
        if name in LOCAL_SIGN_IN:  # the localhost sign-in paths themselves
            continue
        for key, value in env(service).items():
            if isinstance(value, str) and "localhost" in value:
                # only as a default inside ${VAR:-...}
                assert re.search(r"\$\{[A-Z_]+:?-[^}]*localhost", value), (name, key)


def test_mcp_and_agent_export_traces(services):
    """NFR-OBS-001: tracing is wired for both; off unless the endpoint is set."""
    for name in ("core-mcp", "user-agent", "core-mcp-gcp", "user-agent-gcp"):
        assert "OTEL_EXPORTER_OTLP_ENDPOINT" in env(services[name]), name
        assert env(services[name]).get("OTEL_SERVICE_NAME"), name


def test_the_gcp_stack_is_a_profile_beside_the_entra_stack(services):
    """CH-0022 (NFR-PORT-003): profile `gcp` is the local twin of the GCP stack; the default
    services are unchanged and never get Google settings."""
    gcp = {"core-mcp-gcp", "user-agent-gcp", "oauth2-proxy-gcp"}
    for name in gcp:
        assert services[name]["profiles"] == ["gcp"], name
    assert services["oauth2-proxy-gcp-public"]["profiles"] == ["gcp-tunnel"]
    for name in ("core-mcp", "user-agent", "oauth2-proxy", "ui-copilotkit"):
        assert "profiles" not in services[name], name
        assert not [k for k in env(services[name]) if "OAUTH_CLIENT_IDS" in k], name
    assert env(services["user-agent-gcp"])["SDLC_IDENTITY_PROVIDER"] == "google"
    assert env(services["user-agent-gcp"])["SDLC_MCP_URL"] == "http://core-mcp-gcp:8080/mcp"
    for name in ("core-mcp-gcp", "user-agent-gcp"):
        assert not [k for k in env(services[name]) if k.startswith("ENTRA_")], name
        assert "${SDLC_OAUTH_CLIENT_IDS" in env(services[name])["SDLC_OAUTH_CLIENT_IDS"], name


def test_the_gcp_sign_in_passes_the_id_token_to_the_gcp_stack_only(services):
    """The proxy sends the Google ID token (Authorization), not Google's access token, and only to
    the GCP stack's agent and MCP routes; its cookie is not the Entra proxy's."""
    for name in ("oauth2-proxy-gcp", "oauth2-proxy-gcp-public"):
        proxy = env(services[name])
        assert proxy["OAUTH2_PROXY_PROVIDER"] == "google", name
        assert proxy["OAUTH2_PROXY_PASS_AUTHORIZATION_HEADER"] == "true", name
        assert proxy["OAUTH2_PROXY_PASS_ACCESS_TOKEN"] == "false", name
        upstreams = proxy["OAUTH2_PROXY_UPSTREAMS"].split(",")
        assert all("://user-agent-gcp:" in u or "://core-mcp-gcp:" in u for u in upstreams), name
        assert proxy["OAUTH2_PROXY_COOKIE_NAME"] == "_oauth2_proxy_gcp", name
        assert "${SDLC_ALLOWED_DOMAINS" in proxy["OAUTH2_PROXY_EMAIL_DOMAINS"], name
    public = env(services["oauth2-proxy-gcp-public"])
    assert "${SDLC_GCP_APP_HOST" in public["OAUTH2_PROXY_REDIRECT_URL"]
    assert "${SDLC_GCP_MCP_HOST" in env(services["core-mcp-gcp"])["MCP_PUBLIC_URL"]

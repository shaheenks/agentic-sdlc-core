"""Shared fixtures."""

import asyncio
import os
import sys
from pathlib import Path

# Tests never export telemetry, whatever .env says (--env-file .env may set an OTLP endpoint that
# only resolves inside Docker). Cleared before ADK/fastmcp read the environment.
for _var in [v for v in os.environ if v.startswith("OTEL_EXPORTER_OTLP_")]:
    del os.environ[_var]

import pytest
from fastmcp import FastMCP
from sdlc_config import ConfigStore, load_snapshot
from sdlc_mcp_bootstrap.server import build_http_app

from tests.support.config import make_config_dir
from tests.support.entra import TEST_ENV, FakeEntra
from tests.support.servers import build_test_mcp_server, free_port, serve


@pytest.fixture
def entra() -> FakeEntra:
    return FakeEntra()


@pytest.fixture
def config_dir(tmp_path) -> Path:
    """Repo config with a fixed test GroupMap; safe to mutate."""
    return make_config_dir(tmp_path)


@pytest.fixture
def store(config_dir) -> ConfigStore:
    return ConfigStore(lambda: load_snapshot(config_dir, "local", TEST_ENV))


@pytest.fixture
def port() -> int:
    return free_port()


@pytest.fixture
def server(entra, store, port) -> FastMCP:
    return build_test_mcp_server(entra, store, port)


@pytest.fixture
def base_url(server, store, port):
    """Bootstrap MCP server running on a real port (base URL without /mcp), wired as in main()."""
    with serve(build_http_app(server, store), port) as url:
        yield url


@pytest.fixture(scope="session")
def event_loop_policy():
    """psycopg async needs a selector event loop; Windows defaults to Proactor."""
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()

"""Shared fixtures."""

from pathlib import Path

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

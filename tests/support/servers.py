"""Run ASGI apps (MCP server, agent web app) on a real port in a background thread."""

import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import uvicorn
from fastmcp import FastMCP
from fastmcp.server.auth import RemoteAuthProvider
from sdlc_auth.entra import entra_issuer
from sdlc_config import ConfigStore
from sdlc_mcp_bootstrap.server import build_server

from tests.support.entra import TENANT, FakeEntra

REPO_ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP_SKILLS = REPO_ROOT / "skills" / "bootstrap"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def serve(app, port: int) -> Iterator[str]:
    """Serve `app` with uvicorn on 127.0.0.1:port; yields the base URL."""
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "server did not start"
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def build_test_mcp_server(entra: FakeEntra, store: ConfigStore, port: int) -> FastMCP:
    """Bootstrap MCP server wired like production (build_auth), with the fake issuer's keys."""
    auth = RemoteAuthProvider(
        token_verifier=entra.verifier(),
        authorization_servers=[entra_issuer(TENANT)],
        base_url=f"http://127.0.0.1:{port}",
        resource_name="sdlc-mcp",
    )
    return build_server(BOOTSTRAP_SKILLS, store, auth)

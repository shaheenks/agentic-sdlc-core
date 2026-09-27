"""E3: block list (env/<env>/blocked.yaml). A blocked user is refused on every MCP request even with
a valid token, the refusal is audited as `blocked`, and changes apply on config reload."""

import json

import httpx
import pytest
from fastmcp import Client
from fastmcp.server.auth import RemoteAuthProvider
from sdlc_auth.entra import entra_issuer
from sdlc_config import ConfigError, load_snapshot
from sdlc_mcp_bootstrap.server import build_http_app, build_server

from tests.support.entra import G_ENG_ALL, TENANT, TEST_ENV
from tests.support.servers import serve

BLOCKED = "bbbbbbbb-0000-0000-0000-00000000000b"
ALLOWED = "aaaaaaaa-0000-0000-0000-00000000000a"
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


def write_blocklist(config_dir, entries):
    lines = ["apiVersion: sdlc/v1", "kind: BlockList", "blocked:"]
    lines += [f'  - oid: "{oid}"\n    reason: "{reason}"' for oid, reason in entries]
    if not entries:
        lines[-1] = "blocked: []"
    (config_dir / "env/local/blocked.yaml").write_text("\n".join(lines) + "\n")


# --- config -------------------------------------------------------------------------------------


def test_no_file_means_nobody_is_blocked(config_dir):
    assert dict(load_snapshot(config_dir, "local", TEST_ENV).blocked) == {}


def test_blocklist_loads_lower_cased(config_dir):
    write_blocklist(config_dir, [(BLOCKED.upper(), "SEC-1 offboarding")])
    snap = load_snapshot(config_dir, "local", TEST_ENV)
    assert dict(snap.blocked) == {BLOCKED: "SEC-1 offboarding"}
    assert "config/env/local/blocked.yaml" in snap.files  # part of the version and bundles


@pytest.mark.parametrize(
    "body",
    [
        'blocked:\n  - oid: "not-a-guid"\n    reason: "x"\n',
        f'blocked:\n  - oid: "{BLOCKED}"\n',  # reason is required
        # unknown key
        f'blocked:\n  - oid: "{BLOCKED}"\n    reason: "x"\n    until: "2026-12-31"\n',
    ],
)
def test_invalid_blocklists_fail(config_dir, body):
    (config_dir / "env/local/blocked.yaml").write_text(
        f"apiVersion: sdlc/v1\nkind: BlockList\n{body}"
    )
    with pytest.raises(ConfigError, match="blocked.yaml"):
        load_snapshot(config_dir, "local", TEST_ENV)


# --- enforcement --------------------------------------------------------------------------------


@pytest.fixture
def blocking_url(entra, store, port):
    """MCP server whose verifier consults the store's block list, as build_auth(..., store) does."""
    auth = RemoteAuthProvider(
        token_verifier=entra.verifier(blocked_reason=lambda oid: store.current().blocked.get(oid)),
        authorization_servers=[entra_issuer(TENANT)],
        base_url=f"http://127.0.0.1:{port}",
        resource_name="sdlc-mcp",
    )
    with serve(build_http_app(build_server(store, auth), store), port) as url:
        yield url


def tools_list(url, token) -> httpx.Response:
    """Raw request: 401 = refused by authentication; anything else got past it (a valid token
    without the MCP initialize handshake gets 400)."""
    return httpx.post(
        f"{url}/mcp",
        headers={**MCP_HEADERS, "Authorization": f"Bearer {token}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )


async def test_blocked_user_is_refused_and_audited(config_dir, store, entra, blocking_url, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    write_blocklist(config_dir, [(BLOCKED, "SEC-1 offboarding")])
    assert store.reload()
    assert tools_list(blocking_url, entra.token(oid=BLOCKED, groups=[G_ENG_ALL])).status_code == 401
    records = [json.loads(r.getMessage()) for r in caplog.records if r.name == "sdlc.audit"]
    [failure] = [r for r in records if r["event"] == "auth_failure"]
    assert failure["reason"] == "blocked" and failure["claimed"]["oid"] == BLOCKED
    async with Client(f"{blocking_url}/mcp", auth=entra.token(oid=ALLOWED)) as c:
        assert await c.list_tools()  # everyone else is unaffected


async def test_block_and_unblock_apply_on_reload(config_dir, store, entra, blocking_url):
    token = entra.token(oid=BLOCKED, groups=[G_ENG_ALL])
    assert tools_list(blocking_url, token).status_code != 401
    write_blocklist(config_dir, [(BLOCKED, "SEC-2 compromised account")])
    assert store.reload()
    assert tools_list(blocking_url, token).status_code == 401  # same token, next request
    write_blocklist(config_dir, [])
    assert store.reload()
    assert tools_list(blocking_url, token).status_code != 401

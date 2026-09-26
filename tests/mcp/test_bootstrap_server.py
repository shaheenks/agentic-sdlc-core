"""Bootstrap MCP server over real HTTP with Entra-shaped test tokens (no real Entra needed)."""

import json
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import RemoteAuthProvider
from sdlc_auth.entra import entra_issuer
from sdlc_config import ConfigStore, load_snapshot
from sdlc_mcp_bootstrap.server import build_server, discover_skills, parse_skill

from tests.support.entra import (
    G_ENG_ALL,
    G_PAYMENTS_DEVS,
    G_PLATFORM_DEVS,
    TENANT,
    TEST_ENV,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP_SKILLS = REPO_ROOT / "skills" / "bootstrap"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def store(config_dir) -> ConfigStore:
    return ConfigStore(lambda: load_snapshot(config_dir, "local", TEST_ENV))


@pytest.fixture
def port() -> int:
    return _free_port()


@pytest.fixture
def server(entra, store, port) -> FastMCP:
    # Same wrapper as production (build_auth), but with the fake issuer's verifier.
    auth = RemoteAuthProvider(
        token_verifier=entra.verifier(),
        authorization_servers=[entra_issuer(TENANT)],
        base_url=f"http://127.0.0.1:{port}",
        resource_name="sdlc-mcp",
    )
    return build_server(BOOTSTRAP_SKILLS, store, auth)


@pytest.fixture
def base_url(server, port):
    """Run the server's HTTP app with uvicorn in a background thread."""
    uv = uvicorn.Server(
        uvicorn.Config(server.http_app(), host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=uv.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not uv.started:
        assert time.monotonic() < deadline, "server did not start"
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    uv.should_exit = True
    thread.join(timeout=5)


def client(base_url: str, token: str | None) -> Client:
    return Client(f"{base_url}/mcp", auth=token)


# --- authentication -------------------------------------------------------------------------


def test_healthz_is_public_and_reports_config_version(base_url, store):
    body = httpx.get(f"{base_url}/healthz").json()
    assert body["status"] == "ok"
    assert body["config_version"] == store.current().version


@pytest.mark.parametrize("auth_header", [None, "Bearer not-a-jwt"])
def test_mcp_endpoint_rejects_missing_or_invalid_token(base_url, auth_header):
    headers = {"Accept": "application/json, text/event-stream"}
    if auth_header:
        headers["Authorization"] = auth_header
    resp = httpx.post(
        f"{base_url}/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    )
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"].lower().startswith("bearer")


def test_401_points_clients_to_entra(base_url):
    """RFC 9728: the challenge names a metadata URL that exists and lists Entra as the AS."""
    resp = httpx.post(
        f"{base_url}/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={"Accept": "application/json, text/event-stream"},
    )
    challenge = resp.headers["www-authenticate"]
    metadata_url = challenge.split('resource_metadata="')[1].split('"')[0]
    metadata = httpx.get(metadata_url).json()
    assert metadata["authorization_servers"] == [entra_issuer(TENANT)]
    assert metadata["resource"].rstrip("/").endswith("/mcp")


@pytest.mark.parametrize(
    "token_kwargs",
    [{"expires_in": -30}, {"omit": ["scp"]}, {"tid": "99999999-9999-9999-9999-999999999999"}],
)
def test_invalid_entra_tokens_get_401(base_url, entra, token_kwargs):
    resp = httpx.post(
        f"{base_url}/mcp",
        headers={
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {entra.token(**token_kwargs)}",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert resp.status_code == 401


async def test_non_http_transport_without_token_is_denied(server):
    # In-memory transport skips HTTP auth; the audit middleware still refuses the call.
    async with Client(server) as c:
        with pytest.raises(ToolError, match="authentication required"):
            await c.call_tool("ping", {})


# --- tools with a valid token ---------------------------------------------------------------


async def test_stage2_tools(base_url, entra):
    async with client(base_url, entra.token()) as c:
        assert {t.name for t in await c.list_tools()} == {
            "ping",
            "whoami",
            "list_skills",
            "load_skill",
        }
        assert (await c.call_tool("ping", {})).data == "pong"
        listed = (await c.call_tool("list_skills", {})).data
        assert "write-user-story" in {s["name"] for s in listed}
        loaded = (await c.call_tool("load_skill", {"name": "write-user-story"})).data
        assert "Given" in loaded["instructions"]


@pytest.mark.parametrize("name", ["nope", "../agents", "write-user-story/../../CLAUDE"])
async def test_load_unknown_skill_is_rejected(base_url, entra, name):
    async with client(base_url, entra.token()) as c:
        with pytest.raises(ToolError):
            await c.call_tool("load_skill", {"name": name})


async def test_whoami_differs_by_group_membership(base_url, entra, store):
    payments = entra.token(upn="pat@corp.test", groups=[G_ENG_ALL, G_PAYMENTS_DEVS])
    platform = entra.token(
        upn="lee@corp.test",
        groups=[G_ENG_ALL, G_PLATFORM_DEVS, "12345678-0000-0000-0000-00000000dead"],
    )
    async with client(base_url, payments) as c:
        pat = (await c.call_tool("whoami", {})).data
    async with client(base_url, platform) as c:
        lee = (await c.call_tool("whoami", {})).data
    assert pat["upn"] == "pat@corp.test" and pat["groups"] == ["eng-all", "payments-devs"]
    assert lee["groups"] == ["eng-all", "platform-devs"] and lee["unmapped_group_count"] == 1
    assert pat["oid"] != lee["oid"]
    assert pat["group_source"] == "token"
    assert pat["config_version"] == store.current().version


async def test_overage_user_without_graph_gets_no_groups(base_url, entra):
    token = entra.token(omit=["groups"], _claim_names={"groups": "src1"})
    async with client(base_url, token) as c:
        me = (await c.call_tool("whoami", {})).data
    assert me["groups"] == [] and me["group_source"] == "overage_unresolved"


async def test_config_reload_changes_group_mapping(base_url, entra, store, config_dir):
    token = entra.token(groups=[G_PAYMENTS_DEVS])
    groups_file = config_dir / "env/local/groups.yaml"
    groups_file.write_text(groups_file.read_text().replace("payments-devs:", "payments-eng:"))
    assert store.reload()
    async with client(base_url, token) as c:
        me = (await c.call_tool("whoami", {})).data
    assert me["groups"] == ["payments-eng"]
    assert me["config_version"] == store.current().version


# --- audit ----------------------------------------------------------------------------------


async def test_every_tool_call_is_audited(base_url, entra, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    token = entra.token(oid="aaaaaaaa-0000-0000-0000-000000000001", upn="pat@corp.test")
    async with client(base_url, token) as c:
        await c.call_tool("load_skill", {"name": "write-user-story"})
        with pytest.raises(ToolError):
            await c.call_tool("load_skill", {"name": "secret-plan"})
    records = [json.loads(r.getMessage()) for r in caplog.records if r.name == "sdlc.audit"]
    assert [r["outcome"] for r in records] == ["ok", "tool_error"]
    for r in records:
        assert r["oid"] == "aaaaaaaa-0000-0000-0000-000000000001"
        assert r["tool"] == "load_skill" and r["args_hash"].startswith("sha256:")
        assert r["config_version"].startswith("local-")
    # Argument values are hashed, not logged (the tool's own error text is kept separately).
    assert all(
        "secret-plan" not in json.dumps({k: v for k, v in r.items() if k != "error"})
        for r in records
    )


# --- skill parsing ----------------------------------------------------------------------------


def test_skill_without_frontmatter_fails(tmp_path):
    bad = tmp_path / "bad" / "SKILL.md"
    bad.parent.mkdir()
    bad.write_text("# no frontmatter", encoding="utf-8")
    with pytest.raises(ValueError, match="frontmatter"):
        parse_skill(bad)


def test_duplicate_skill_names_fail(tmp_path):
    for folder in ("a", "b"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "SKILL.md").write_text(
            "---\nname: dup\ndescription: d\n---\nbody", encoding="utf-8"
        )
    with pytest.raises(ValueError, match="duplicate"):
        discover_skills(tmp_path)

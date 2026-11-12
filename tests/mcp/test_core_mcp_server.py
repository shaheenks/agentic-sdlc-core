"""Core MCP server over real HTTP with Entra-shaped test tokens (no real Entra needed)."""

import json

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from sdlc_auth.entra import entra_issuer

from tests.support.entra import G_ENG_ALL, G_PAYMENTS_DEVS, G_PLATFORM_DEVS, TENANT

# Fixtures `store`, `server`, `base_url` come from tests/conftest.py.


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
            "get_agent_context",
            "resolve_team",  # version-03 P10 G9
            # version-03 P5: always registered (they answer "not configured" without a store)
            "save_artifact",
            "list_artifacts",
            "read_artifact",
            "delete_artifact",
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


async def test_whoami_differs_by_app_roles(base_url, entra, store):
    payments = entra.token(upn="pat@corp.test", roles=[G_ENG_ALL, G_PAYMENTS_DEVS])
    platform = entra.token(upn="lee@corp.test", roles=[G_ENG_ALL, G_PLATFORM_DEVS])
    async with client(base_url, payments) as c:
        pat = (await c.call_tool("whoami", {"explain": True})).data
    async with client(base_url, platform) as c:
        lee = (await c.call_tool("whoami", {"explain": True})).data
    assert pat["upn"] == "pat@corp.test" and pat["app_roles"] == sorted(
        [G_ENG_ALL, G_PAYMENTS_DEVS]
    )
    assert set(pat["policy"]["teams"]) == {"payments"}
    assert set(lee["policy"]["teams"]) == {"sdlc-platform"}
    assert pat["oid"] != lee["oid"]
    assert "groups" not in pat and "group_source" not in pat  # CH-0011
    assert pat["config_version"] == store.current().version


async def test_config_reload_changes_app_role_mapping(base_url, entra, store, config_dir):
    token = entra.token(roles=[G_PAYMENTS_DEVS])
    team_file = config_dir / "teams/payments.yaml"
    original = team_file.read_text()

    # A team role in a global binding is rejected; the old version keeps serving.
    good_version = store.current().version
    roles_file = config_dir / "roles.yaml"
    roles_original = roles_file.read_text()
    roles_file.write_text(
        roles_original.replace(
            "roles:\n  signed-in:",
            "  - app_role: SDLC.X\n    roles: [member]\nroles:\n  signed-in:",
            1,
        )
    )
    assert store.reload() is False
    assert "is a platform role" in store.last_error
    assert store.current().version == good_version
    roles_file.write_text(roles_original)

    # Moving the team to another app role value: the old value no longer grants the team.
    team_file.write_text(original.replace("SDLC.Payments.Member", "SDLC.Payments.Engineer"))
    assert store.reload()
    async with client(base_url, token) as c:
        me = (await c.call_tool("whoami", {"explain": True})).data
    assert me["policy"]["teams"] == {}
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
    records = [r for r in records if r["event"] == "tool_call"]
    assert [r["outcome"] for r in records] == ["ok", "denied"]  # hidden skill = policy deny
    for r in records:
        assert r["oid"] == "aaaaaaaa-0000-0000-0000-000000000001"
        assert r["tool"] == "load_skill" and r["args_hash"].startswith("sha256:")
        assert r["config_version"].startswith("local-")
    # Argument values are hashed, not logged (the tool's own error text is kept separately).
    assert all(
        "secret-plan" not in json.dumps({k: v for k, v in r.items() if k != "error"})
        for r in records
    )

"""user_agent_mcp end to end, through HTTP: identity, policy, isolation and audit (phase 1 exit gate)."""

import base64
import json
import logging
import os
from pathlib import Path

import pytest
from sdlc_config_store import ConfigStore, DirSource, make_bundle, make_pointer
from sdlc_identity import GoogleTokens, Rejected
from sdlc_logging import AUDIT_LOGGER
from starlette.testclient import TestClient
from user_agent_mcp import SERVICE, create_app, create_platform
from user_agent_mcp.settings import Settings

NOW = 1_800_000_000
PROTOCOL = "2026-07-28"
CONFIG = {
    "platform": {"artifacts": {"max_bytes": 1000, "content_types": ["text/markdown", "text/plain"]}},
    "tool_groups": {
        "identity": {"description": "-", "tools": ["whoami"]},
        "artifacts": {
            "description": "-",
            "tools": ["artifact_list", "artifact_read", "artifact_save", "artifact_delete"],
        },
        "connections": {"description": "-", "tools": ["connection_list", "connection_start", "connection_revoke"]},
        "connection_secrets": {"description": "-", "tools": ["connection_save"]},
    },
    "surfaces": {
        "sdlc_ui": {"description": "-", "tool_groups": ["identity", "artifacts", "connections", "connection_secrets"]},
        "gemini_enterprise": {"description": "-", "tool_groups": ["identity", "artifacts", "connections"]},
    },
    "teams": {"payments": {"name": "Payments", "description": "-", "roles": {"member": ["payments@example.test"]}}},
    "user_groups": {},
    "grants": [
        {
            "id": "everyone-basics",
            "description": "-",
            "tool_groups": ["identity", "artifacts", "connections", "connection_secrets"],
            "to": {"everyone": True},
        }
    ],
    "rate_limits": {"tool_calls": {"per_user_per_minute": 50, "per_team_per_minute": 500}},
    "providers": {
        "github": {"name": "GitHub", "system": "github", "edition": "cloud", "base_url": "https://api.github.com"},
        "jira_dc": {"name": "Jira Data Center", "system": "jira", "edition": "data_center"},
    },
    "identity": {
        "allowed_domains": ["example.test"],
        "clients": {"sdlc_ui": ["ui-client"], "gemini_enterprise": ["ge-client"]},
        "directory": {"mode": "static"},
    },
    "directory_users": {"ada@example.test": ["payments@example.test"]},
    "blocked": [],
}
# Bearer token -> what Google's introspection would answer.
USERS = {
    "ya29.ada-ui": {"sub": "1001", "email": "ada@example.test", "aud": "ui-client"},
    "ya29.ada-ge": {"sub": "1001", "email": "ada@example.test", "aud": "ge-client"},
    "ya29.grace-ui": {"sub": "1002", "email": "grace@example.test", "aud": "ui-client"},
    "ya29.mallory-other-client": {"sub": "1003", "email": "mallory@example.test", "aud": "someone-elses-client"},
}
SECRET = "ghp_this-is-the-users-token-and-must-never-be-logged"


async def introspect(token: str) -> dict:
    if token not in USERS:
        raise Rejected("invalid_token")
    return {
        **USERS[token],
        "email_verified": "true",
        "scope": "openid https://www.googleapis.com/auth/userinfo.email",
        "exp": str(NOW + 3600),
    }


def publish(root: Path, config: dict) -> None:
    source = DirSource(root)
    doc = make_bundle("test", config)
    source.write(f"bundles/{doc['version']}.json", json.dumps(doc).encode())
    source.write("active.json", json.dumps(make_pointer(doc["version"], "tester", None)).encode())


@pytest.fixture
def env(tmp_path):
    config_root, store_root = tmp_path / "config", tmp_path / "store"
    publish(config_root, CONFIG)
    settings = Settings(
        env="test",
        config_source=str(config_root),
        store_root=store_root,
        public_url="http://testserver",
        sdlc_ui_url="https://ui.example.test",
        encryption_key=os.urandom(32),
        encryption_key_version="1",
        config_refresh_seconds=0,
    )
    platform = create_platform(settings, tokens=GoogleTokens(introspect=introspect, clock=lambda: NOW))
    platform.store.load()
    with TestClient(create_app(platform=platform)) as client:
        yield client, platform, config_root, store_root


def mcp(client, token, method, params=None):
    params = dict(params or {})
    params["_meta"] = {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL,
        "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "1"},
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL,
    }
    if method == "tools/call":
        headers["Mcp-Method"] = "tools/call"
        headers["Mcp-Name"] = params["name"]
    else:
        headers["Mcp-Method"] = method
    return client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, headers=headers)


def call(client, token, tool, /, **arguments):
    response = mcp(client, token, "tools/call", {"name": tool, "arguments": arguments})
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    return json.loads(result["content"][0]["text"]), result.get("isError", False)


def api(client, token, method, path, **kwargs):
    return client.request(method, path, headers={"Authorization": f"Bearer {token}"}, **kwargs)


def test_healthz_and_metadata_are_public(env):
    client, *_ = env
    assert client.get("/healthz").json()["service"] == SERVICE
    meta = client.get("/.well-known/oauth-protected-resource").json()
    assert meta["authorization_servers"] == ["https://accounts.google.com"]


@pytest.mark.parametrize("token", [None, "ya29.mallory-other-client", "ya29.unknown"])
def test_unverified_or_undeclared_callers_get_401(env, token, caplog):
    client, *_ = env
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER):
        assert client.post("/mcp", json={}, headers=headers).status_code == 401
        response = client.get("/api/me", headers=headers)
    assert response.status_code == 401
    assert "resource_metadata=" in response.headers["www-authenticate"]
    reasons = {r.reason for r in caplog.records if getattr(r, "event", "") == "auth.denied"}
    assert reasons == {{None: "no_token", "ya29.unknown": "invalid_token"}.get(token, "undeclared_client")}


def test_tools_listed_per_surface(env):
    client, *_ = env
    names = lambda token: {t["name"] for t in mcp(client, token, "tools/list").json()["result"]["tools"]}  # noqa: E731
    ui = names("ya29.ada-ui")
    assert "artifact_save" in ui and "connection_start" in ui
    assert "connection_save" not in ui  # the secret is entered on the secure page only, never through MCP
    assert names("ya29.ada-ge") == ui


def test_whoami_shows_identity_teams_and_access(env):
    client, *_ = env
    me, error = call(client, "ya29.ada-ui", "whoami")
    assert not error
    assert me["user_id"] == "1001" and me["teams"] == {"payments": ["member"]}
    assert me["access"]["surface"] == "sdlc_ui"


def test_two_users_cannot_reach_each_others_artifacts(env):
    client, *_ = env
    saved, error = call(client, "ya29.ada-ui", "artifact_save", name="design-notes", content="# Ada's notes")
    assert not error and saved["version"] == 1 and saved["owner"] == "1001"
    call(client, "ya29.ada-ui", "artifact_save", name="design-notes", content="# Ada's notes v2")

    listed, _ = call(client, "ya29.grace-ui", "artifact_list")
    assert listed == {"artifacts": []}
    for tool in ("artifact_read", "artifact_delete"):
        result, error = call(client, "ya29.grace-ui", tool, name="design-notes")
        assert error and result["error"] == "not_found"
    assert api(client, "ya29.grace-ui", "GET", "/api/artifacts/design-notes").status_code == 404
    assert api(client, "ya29.grace-ui", "DELETE", "/api/artifacts/design-notes").status_code == 404

    mine, _ = call(client, "ya29.ada-ge", "artifact_read", name="design-notes")  # same user, other surface
    assert mine["content"] == "# Ada's notes v2" and mine["versions"] == [1, 2]
    first, _ = call(client, "ya29.ada-ui", "artifact_read", name="design-notes", version=1)
    assert first["content"] == "# Ada's notes"


@pytest.mark.parametrize("name", ["../1002/x", "..", "a/b", "x" * 101, ""])
def test_artifact_names_cannot_leave_the_users_prefix(env, name):
    client, *_ = env
    result, error = call(client, "ya29.ada-ui", "artifact_save", name=name, content="x")
    assert error and result["error"] in {"invalid_name", "invalid_argument"}


def test_artifact_limits(env):
    client, *_ = env
    too_big, _ = call(client, "ya29.ada-ui", "artifact_save", name="big", content="x" * 1001)
    assert too_big["error"] == "too_large"
    wrong_type, _ = call(client, "ya29.ada-ui", "artifact_save", name="img", content="x", content_type="image/png")
    assert wrong_type["error"] == "invalid_type"


def test_connections_are_per_user_and_never_return_the_secret(env, caplog):
    client, platform, _, store_root = env
    started, _ = call(client, "ya29.ada-ge", "connection_start", provider="github")
    assert started["entry_url"] == "https://ui.example.test/connections/github"

    with caplog.at_level(logging.DEBUG):
        saved = api(client, "ya29.ada-ui", "PUT", "/api/connections/github", json={"secret": SECRET, "account": "ada"})
        assert saved.status_code == 200 and SECRET not in saved.text
        # Gemini Enterprise has no connection_secrets tool group: no secret entry there.
        assert api(client, "ya29.ada-ge", "PUT", "/api/connections/github", json={"secret": SECRET}).status_code == 403
        listed, _ = call(client, "ya29.ada-ui", "connection_list")
        assert [c["provider"] for c in listed["connections"]] == ["github"] and SECRET not in json.dumps(listed)
        assert call(client, "ya29.grace-ui", "connection_list")[0]["connections"] == []
        revoked, error = call(client, "ya29.grace-ui", "connection_revoke", provider="github")
        assert error and revoked["error"] == "not_found"

    stored = next((store_root / "secrets" / "users" / "1001").iterdir()).read_text()
    assert SECRET not in stored
    assert platform.connections.secret("1001", "github") == SECRET
    assert SECRET not in caplog.text

    assert call(client, "ya29.ada-ui", "connection_revoke", provider="github")[0]["revoked"] is True
    assert call(client, "ya29.ada-ui", "connection_list")[0]["connections"] == []


def test_a_secret_copied_to_another_user_cannot_be_decrypted(env):
    client, platform, _, store_root = env
    api(client, "ya29.ada-ui", "PUT", "/api/connections/github", json={"secret": SECRET})
    target = store_root / "secrets" / "users" / "1002"
    target.mkdir(parents=True)
    (target / "github.json").write_bytes((store_root / "secrets" / "users" / "1001" / "github.json").read_bytes())
    with pytest.raises(Exception, match="cannot be decrypted"):
        platform.connections.secret("1002", "github")


def test_data_center_connection_needs_its_server_url(env):
    client, *_ = env
    response = api(client, "ya29.ada-ui", "PUT", "/api/connections/jira_dc", json={"secret": "x"})
    assert response.status_code == 400 and response.json()["error"] == "invalid_base_url"


def test_every_call_is_audited_without_argument_values(env, caplog):
    client, *_ = env
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER):
        call(client, "ya29.ada-ui", "artifact_save", name="secret-plan", content="the launch date is March")
        call(client, "ya29.ada-ui", "no_such_tool")
    records = [r for r in caplog.records if getattr(r, "event", "") == "tool.call"]
    assert [(r.tool, r.decision) for r in records] == [("artifact_save", "allow"), ("no_such_tool", "deny")]
    saved = records[0]
    assert (saved.user_id, saved.surface, saved.log_type) == ("1001", "sdlc_ui", "sdlc_audit")
    assert saved.rule == "grant:everyone-basics/tool_group:artifacts/surface:sdlc_ui" and saved.config_version
    text = "\n".join(json.dumps(vars(r), default=str) for r in caplog.records)
    assert "secret-plan" not in text and "launch date" not in text and "ada@example.test" not in text


def test_run_and_step_headers_reach_the_audit_and_the_artifact(env, caplog):
    client, *_ = env
    headers = {"Authorization": "Bearer ya29.ada-ui", "X-SDLC-Run-Id": "run-42", "X-SDLC-Step": "draft"}
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER):
        response = client.get("/api/artifacts", headers=headers)
    assert response.status_code == 200
    record = next(r for r in caplog.records if getattr(r, "event", "") == "tool.call")
    assert (record.run_id, record.step) == ("run-42", "draft")


def test_activated_grant_change_applies_without_restart(env):
    client, _, config_root, _ = env
    revoked = {**CONFIG, "grants": [{**CONFIG["grants"][0], "tool_groups": ["identity"]}]}
    publish(config_root, revoked)
    result, error = call(client, "ya29.ada-ui", "artifact_list")
    assert error and result["error"] == "not_allowed"


def test_block_list_applies_once_active(env):
    client, _, config_root, _ = env
    publish(config_root, {**CONFIG, "blocked": [{"user_id": "1001", "reason": "test"}]})
    assert api(client, "ya29.ada-ui", "GET", "/api/me").status_code == 401
    assert api(client, "ya29.grace-ui", "GET", "/api/me").status_code == 200


def test_rate_limit_refuses_with_a_reason(env):
    client, _, config_root, _ = env
    publish(
        config_root, {**CONFIG, "rate_limits": {"tool_calls": {"per_user_per_minute": 2, "per_team_per_minute": 9}}}
    )
    results = [call(client, "ya29.ada-ui", "whoami")[0] for _ in range(3)]
    assert results[2]["error"] == "rate_limited"
    assert api(client, "ya29.ada-ui", "GET", "/api/me").status_code == 429


def test_service_refuses_to_start_without_a_bundle(tmp_path):
    settings = Settings("test", str(tmp_path / "none"), tmp_path, "http://x", None, None, "1")
    with pytest.raises(Exception, match="active|No such file|cannot find"):
        create_app(settings)


def test_encryption_key_must_be_32_bytes():
    environ = {
        "CONFIG_SOURCE": "x",
        "STORE_MOUNT_PATH": "y",
        "DATA_ENCRYPTION_KEY": base64.b64encode(b"short").decode(),
    }
    with pytest.raises(SystemExit, match="32 bytes"):
        Settings.from_env(environ)


def test_config_store_is_the_one_loaded(env):
    _, platform, *_ = env
    assert isinstance(platform.store, ConfigStore)

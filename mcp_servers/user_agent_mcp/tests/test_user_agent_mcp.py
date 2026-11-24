"""user_agent_mcp end to end, through HTTP: identity, policy, isolation and audit (phase 1 exit gate), with
users forwarded by declared callers (DEC-0010)."""

import base64
import json
import logging
import os
from pathlib import Path

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sdlc_config_store import ConfigStore, DirSource, make_bundle, make_pointer
from sdlc_identity import GoogleTokens
from sdlc_logging import AUDIT_LOGGER
from starlette.testclient import TestClient
from user_agent_mcp import SERVICE, create_app, create_platform
from user_agent_mcp.knowledge import KnowledgeClient
from user_agent_mcp.settings import Settings

NOW = 1_800_000_000
PROTOCOL = "2026-07-28"
PUBLIC_URL = "http://testserver"
UI_ACCOUNT = "sdlc-ui@proj.iam.gserviceaccount.com"
AGENT_ACCOUNT = "user-agent@proj.iam.gserviceaccount.com"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
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
        "user_agent": {"description": "-", "tool_groups": ["identity", "artifacts", "connections"]},
    },
    "teams": {"payments": {"name": "Payments", "description": "-", "roles": ["member", "lead"]}},
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
        "mode": "caller_token",
        "allowed_domains": ["example.test"],
        "callers": {"sdlc_ui": [UI_ACCOUNT], "user_agent": [AGENT_ACCOUNT]},
        "clients": {},
    },
    "members": {"ada@example.test": {"teams": {"payments": ["member"]}, "user_groups": []}},
    "blocked": [],
}


def caller_token(account: str, aud: str = PUBLIC_URL) -> str:
    claims = {"iss": "https://accounts.google.com", "aud": aud, "sub": "9" + str(len(account)), "email": account}
    return jwt.encode({**claims, "email_verified": True, "exp": NOW + 3600}, KEY, algorithm="RS256")


def verify_locally(token: str) -> dict:
    options = {"verify_aud": False, "verify_exp": False}
    return jwt.decode(token, KEY.public_key(), algorithms=["RS256"], options=options)


ADA = {"X-SDLC-User-Id": "accounts.google.com:1001", "X-SDLC-User-Email": "ada@example.test"}
GRACE = {"X-SDLC-User-Id": "1002", "X-SDLC-User-Email": "grace@example.test"}
# Who calls -> the headers the caller sends.
WHO = {
    "ada-ui": {"Authorization": f"Bearer {caller_token(UI_ACCOUNT)}", **ADA},
    "ada-agent": {"Authorization": f"Bearer {caller_token(AGENT_ACCOUNT)}", **ADA},
    "grace-ui": {"Authorization": f"Bearer {caller_token(UI_ACCOUNT)}", **GRACE},
    "ada-undeclared-caller": {"Authorization": f"Bearer {caller_token('x@proj.iam.gserviceaccount.com')}", **ADA},
    "ada-token-for-another-service": {"Authorization": f"Bearer {caller_token(UI_ACCOUNT, 'https://x.test')}", **ADA},
    "ada-without-proof": ADA,
    "nobody": {},
}
SECRET = "ghp_this-is-the-users-token-and-must-never-be-logged"


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
        public_url=PUBLIC_URL,
        sdlc_ui_url="https://ui.example.test",
        encryption_key=os.urandom(32),
        encryption_key_version="1",
        config_refresh_seconds=0,
    )
    platform = create_platform(settings, tokens=GoogleTokens(verify_id_token=verify_locally, clock=lambda: NOW))
    platform.store.load()
    with TestClient(create_app(platform=platform)) as client:
        yield client, platform, config_root, store_root


def mcp(client, who, method, params=None):
    params = dict(params or {})
    params["_meta"] = {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL,
        "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "1"},
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    headers = {**WHO[who], "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": PROTOCOL}
    if method == "tools/call":
        headers["Mcp-Method"] = "tools/call"
        headers["Mcp-Name"] = params["name"]
    else:
        headers["Mcp-Method"] = method
    return client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, headers=headers)


def call(client, who, tool, /, **arguments):
    response = mcp(client, who, "tools/call", {"name": tool, "arguments": arguments})
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    return json.loads(result["content"][0]["text"]), result.get("isError", False)


def api(client, who, method, path, **kwargs):
    return client.request(method, path, headers=WHO[who], **kwargs)


def test_healthz_and_metadata_are_public(env):
    client, *_ = env
    assert client.get("/healthz").json()["service"] == SERVICE
    meta = client.get("/.well-known/oauth-protected-resource").json()
    assert meta["authorization_servers"] == ["https://accounts.google.com"]


@pytest.mark.parametrize(
    ("who", "reason"),
    [
        ("nobody", "no_token"),
        ("ada-without-proof", "no_token"),
        ("ada-undeclared-caller", "undeclared_caller"),
        ("ada-token-for-another-service", "wrong_audience"),
    ],
)
def test_users_not_forwarded_by_a_declared_caller_get_401(env, who, reason, caplog):
    client, *_ = env
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER):
        assert client.post("/mcp", json={}, headers=WHO[who]).status_code == 401
        response = client.get("/api/me", headers=WHO[who])
    assert response.status_code == 401
    reasons = {r.reason for r in caplog.records if getattr(r, "event", "") == "auth.denied"}
    assert reasons == {reason}


def test_trusted_header_mode_is_refused_outside_local(env):
    client, _, config_root, _ = env
    publish(config_root, {**CONFIG, "identity": {**CONFIG["identity"], "mode": "trusted_header"}})
    assert client.get("/api/me", headers={**ADA, "X-SDLC-Surface": "sdlc_ui"}).status_code == 401


def test_tools_listed_per_surface(env):
    client, *_ = env
    names = lambda token: {t["name"] for t in mcp(client, token, "tools/list").json()["result"]["tools"]}  # noqa: E731
    ui = names("ada-ui")
    assert "artifact_save" in ui and "connection_start" in ui
    assert "connection_save" not in ui  # the secret is entered on the secure page only, never through MCP
    assert names("ada-agent") == ui


def test_whoami_shows_identity_teams_and_access(env):
    client, *_ = env
    me, error = call(client, "ada-ui", "whoami")
    assert not error
    assert me["user_id"] == "1001" and me["teams"] == {"payments": ["member"]}
    assert me["access"]["surface"] == "sdlc_ui"


def test_two_users_cannot_reach_each_others_artifacts(env):
    client, *_ = env
    saved, error = call(client, "ada-ui", "artifact_save", name="design-notes", content="# Ada's notes")
    assert not error and saved["version"] == 1 and saved["owner"] == "1001"
    call(client, "ada-ui", "artifact_save", name="design-notes", content="# Ada's notes v2")

    listed, _ = call(client, "grace-ui", "artifact_list")
    assert listed == {"artifacts": []}
    for tool in ("artifact_read", "artifact_delete"):
        result, error = call(client, "grace-ui", tool, name="design-notes")
        assert error and result["error"] == "not_found"
    assert api(client, "grace-ui", "GET", "/api/artifacts/design-notes").status_code == 404
    assert api(client, "grace-ui", "DELETE", "/api/artifacts/design-notes").status_code == 404

    mine, _ = call(client, "ada-agent", "artifact_read", name="design-notes")  # same user, through the agent
    assert mine["content"] == "# Ada's notes v2" and mine["versions"] == [1, 2]
    first, _ = call(client, "ada-ui", "artifact_read", name="design-notes", version=1)
    assert first["content"] == "# Ada's notes"


@pytest.mark.parametrize("name", ["../1002/x", "..", "a/b", "x" * 101, ""])
def test_artifact_names_cannot_leave_the_users_prefix(env, name):
    client, *_ = env
    result, error = call(client, "ada-ui", "artifact_save", name=name, content="x")
    assert error and result["error"] in {"invalid_name", "invalid_argument"}


def test_artifact_limits(env):
    client, *_ = env
    too_big, _ = call(client, "ada-ui", "artifact_save", name="big", content="x" * 1001)
    assert too_big["error"] == "too_large"
    wrong_type, _ = call(client, "ada-ui", "artifact_save", name="img", content="x", content_type="image/png")
    assert wrong_type["error"] == "invalid_type"


def test_connections_are_per_user_and_never_return_the_secret(env, caplog):
    client, platform, _, store_root = env
    started, _ = call(client, "ada-agent", "connection_start", provider="github")
    assert started["entry_url"] == "https://ui.example.test/connections/github"

    with caplog.at_level(logging.DEBUG):
        saved = api(client, "ada-ui", "PUT", "/api/connections/github", json={"secret": SECRET, "account": "ada"})
        assert saved.status_code == 200 and SECRET not in saved.text
        # The agent has no connection_secrets tool group: secrets are entered in sdlc_ui only.
        assert api(client, "ada-agent", "PUT", "/api/connections/github", json={"secret": SECRET}).status_code == 403
        listed, _ = call(client, "ada-ui", "connection_list")
        assert [c["provider"] for c in listed["connections"]] == ["github"] and SECRET not in json.dumps(listed)
        assert call(client, "grace-ui", "connection_list")[0]["connections"] == []
        revoked, error = call(client, "grace-ui", "connection_revoke", provider="github")
        assert error and revoked["error"] == "not_found"

    stored = next((store_root / "secrets" / "users" / "1001").iterdir()).read_text()
    assert SECRET not in stored
    assert platform.connections.secret("1001", "github") == SECRET
    assert SECRET not in caplog.text

    assert call(client, "ada-ui", "connection_revoke", provider="github")[0]["revoked"] is True
    assert call(client, "ada-ui", "connection_list")[0]["connections"] == []


def test_a_secret_copied_to_another_user_cannot_be_decrypted(env):
    client, platform, _, store_root = env
    api(client, "ada-ui", "PUT", "/api/connections/github", json={"secret": SECRET})
    target = store_root / "secrets" / "users" / "1002"
    target.mkdir(parents=True)
    (target / "github.json").write_bytes((store_root / "secrets" / "users" / "1001" / "github.json").read_bytes())
    with pytest.raises(Exception, match="cannot be decrypted"):
        platform.connections.secret("1002", "github")


def test_data_center_connection_needs_its_server_url(env):
    client, *_ = env
    response = api(client, "ada-ui", "PUT", "/api/connections/jira_dc", json={"secret": "x"})
    assert response.status_code == 400 and response.json()["error"] == "invalid_base_url"


def test_every_call_is_audited_without_argument_values(env, caplog):
    client, *_ = env
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER):
        call(client, "ada-ui", "artifact_save", name="secret-plan", content="the launch date is March")
        call(client, "ada-ui", "no_such_tool")
    records = [r for r in caplog.records if getattr(r, "event", "") == "tool.call"]
    assert [(r.tool, r.decision) for r in records] == [("artifact_save", "allow"), ("no_such_tool", "deny")]
    saved = records[0]
    assert (saved.user_id, saved.surface, saved.log_type) == ("1001", "sdlc_ui", "sdlc_audit")
    assert saved.rule == "grant:everyone-basics/tool_group:artifacts/surface:sdlc_ui" and saved.config_version
    text = "\n".join(json.dumps(vars(r), default=str) for r in caplog.records)
    assert "secret-plan" not in text and "launch date" not in text and "ada@example.test" not in text


def test_run_and_step_headers_reach_the_audit_and_the_artifact(env, caplog):
    client, *_ = env
    headers = {**WHO["ada-ui"], "X-SDLC-Run-Id": "run-42", "X-SDLC-Step": "draft"}
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER):
        response = client.get("/api/artifacts", headers=headers)
    assert response.status_code == 200
    record = next(r for r in caplog.records if getattr(r, "event", "") == "tool.call")
    assert (record.run_id, record.step) == ("run-42", "draft")


def test_activated_grant_change_applies_without_restart(env):
    client, _, config_root, _ = env
    revoked = {**CONFIG, "grants": [{**CONFIG["grants"][0], "tool_groups": ["identity"]}]}
    publish(config_root, revoked)
    result, error = call(client, "ada-ui", "artifact_list")
    assert error and result["error"] == "not_allowed"


def test_block_list_applies_once_active(env):
    client, _, config_root, _ = env
    publish(config_root, {**CONFIG, "blocked": [{"user_id": "1001", "reason": "test"}]})
    assert api(client, "ada-ui", "GET", "/api/me").status_code == 401
    assert api(client, "grace-ui", "GET", "/api/me").status_code == 200


def test_rate_limit_refuses_with_a_reason(env):
    client, _, config_root, _ = env
    publish(
        config_root, {**CONFIG, "rate_limits": {"tool_calls": {"per_user_per_minute": 2, "per_team_per_minute": 9}}}
    )
    results = [call(client, "ada-ui", "whoami")[0] for _ in range(3)]
    assert results[2]["error"] == "rate_limited"
    assert api(client, "ada-ui", "GET", "/api/me").status_code == 429


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


# Knowledge (FR-KNOW-002, FR-KNOW-004, FR-AUTHZ-004; DEC-0011) ----------------------------------------------

KNOWLEDGE_URL = "https://knowledge.example.test"
KNOWLEDGE_CONFIG = {
    **CONFIG,
    "tool_groups": {
        **CONFIG["tool_groups"],
        "knowledge": {"description": "-", "tools": ["knowledge_search", "knowledge_graph"]},
    },
    "surfaces": {
        "sdlc_ui": {"description": "-", "tool_groups": [*CONFIG["surfaces"]["sdlc_ui"]["tool_groups"], "knowledge"]},
        "user_agent": {
            "description": "-",
            "tool_groups": [*CONFIG["surfaces"]["user_agent"]["tool_groups"], "knowledge"],
        },
    },
    "teams": {**CONFIG["teams"], "platform": {"name": "Platform", "description": "-", "roles": ["member"]}},
    "sources": {"handbook": {}, "payments-repo": {}, "platform-repo": {}},
    "grants": [
        {**CONFIG["grants"][0], "tool_groups": [*CONFIG["grants"][0]["tool_groups"], "knowledge"]},
        {"id": "handbook", "description": "-", "sources": ["handbook"], "to": {"everyone": True}},
        {"id": "payments-code", "description": "-", "sources": ["payments-repo"], "to": {"teams": ["payments"]}},
        {"id": "platform-code", "description": "-", "sources": ["platform-repo"], "to": {"teams": ["platform"]}},
    ],
    "members": {
        "ada@example.test": {"teams": {"payments": ["member"], "platform": ["member"]}, "user_groups": []},
    },
}


@pytest.fixture
def kenv(tmp_path):
    """user_agent_mcp with Knowledge Search faked: each request it receives is recorded."""
    config_root = tmp_path / "config"
    publish(config_root, KNOWLEDGE_CONFIG)
    received = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        received.append((request.url.path, body))
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": [{"source_id": s} for s in body["filter"]["sources"]]})
        return httpx.Response(200, json={"seeds": [], "nodes": [], "edges": []})

    settings = Settings("test", str(config_root), tmp_path / "store", PUBLIC_URL, None, None, "1", 0)
    knowledge = KnowledgeClient(KNOWLEDGE_URL, "none", http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    platform = create_platform(
        settings, tokens=GoogleTokens(verify_id_token=verify_locally, clock=lambda: NOW), knowledge=knowledge
    )
    platform.store.load()
    with TestClient(create_app(platform=platform)) as client:
        yield client, received


def kcall(client, headers, tool, **arguments):
    params = {
        "name": tool,
        "arguments": arguments,
        "_meta": {
            "io.modelcontextprotocol/protocolVersion": PROTOCOL,
            "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "1"},
            "io.modelcontextprotocol/clientCapabilities": {},
        },
    }
    headers = {
        **headers,
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL,
        "Mcp-Method": "tools/call",
        "Mcp-Name": tool,
    }
    response = client.post(
        "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params}, headers=headers
    )
    return response


def test_chat_searches_every_source_the_user_may_read(kenv):
    client, received = kenv
    response = kcall(client, WHO["ada-agent"], "knowledge_search", query="refund flow")
    result = json.loads(response.json()["result"]["content"][0]["text"])
    assert result["team"] is None
    assert received == [
        (
            "/search",
            {
                "query": "refund flow",
                "mode": "hybrid",
                "limit": 8,
                "filter": {"sources": ["handbook", "payments-repo", "platform-repo"]},
            },
        )
    ]


def test_a_team_run_searches_only_its_teams_sources_and_arguments_cannot_widen_it(kenv):
    client, received = kenv
    headers = {**WHO["ada-agent"], "X-SDLC-Team": "payments"}
    kcall(client, headers, "knowledge_search", query="refunds", sources=["platform-repo"], filter={"sources": ["x"]})
    kcall(client, headers, "knowledge_graph", name="Ledger", depth=2)
    assert [body["filter"]["sources"] for _, body in received] == [["handbook", "payments-repo"]] * 2


def test_a_team_the_user_is_not_in_is_refused(kenv, caplog):
    client, received = kenv
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER):
        response = kcall(client, {**WHO["ada-agent"], "X-SDLC-Team": "risk"}, "knowledge_search", query="x")
    assert response.status_code == 403 and received == []
    assert any(getattr(r, "reason", "") == "not_a_team_member" for r in caplog.records)


def test_knowledge_arguments_never_reach_the_audit_log(kenv, caplog):
    client, _ = kenv
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER):
        kcall(client, WHO["ada-agent"], "knowledge_search", query="a very private question")
    assert "a very private question" not in caplog.text
    assert any(getattr(r, "tool", "") == "knowledge_search" for r in caplog.records)


def test_knowledge_without_a_search_service_is_unavailable(env):
    client, *_ = env
    publish(env[2], {**KNOWLEDGE_CONFIG, "members": CONFIG["members"]})
    result, error = call(client, "ada-agent", "knowledge_search", query="x")
    assert error and result["error"] == "knowledge_unavailable"

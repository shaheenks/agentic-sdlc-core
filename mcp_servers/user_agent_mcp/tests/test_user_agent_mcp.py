"""user_agent_mcp end to end, through HTTP: identity, policy, isolation and audit (phase 1 exit gate), with
users forwarded by declared callers (DEC-0010)."""

import base64
import json
import logging
import os
import re
from pathlib import Path

import httpx
import jwt
import pytest
import yaml
from cryptography.hazmat.primitives.asymmetric import rsa
from sdlc_config_store import ConfigStore, DirSource, make_bundle, make_pointer
from sdlc_connectors.testing import FakeGitHub
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
        "connections": {
            "description": "-",
            "tools": ["connection_list", "connection_start", "connection_revoke", "connection_test"],
        },
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
        "jira_cloud": {"name": "Jira Cloud", "system": "jira", "edition": "cloud"},
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


REAL_CLIENT = httpx.Client  # before any fixture replaces it


class Providers:
    """The providers' sign-in endpoints, faked: a saved token is checked against them. SECRET signs in as ada;
    any other token is refused; anything else is unknown here."""

    def __init__(self):
        self.revoked = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        token = request.headers.get("authorization", "")
        ok = SECRET in token and not self.revoked
        if request.url.path == "/user":  # GitHub
            return httpx.Response(200, json={"login": "ada-gh"}) if ok else httpx.Response(401)
        return httpx.Response(404)


@pytest.fixture
def providers(monkeypatch):
    fake = Providers()
    real_client = REAL_CLIENT
    monkeypatch.setattr(
        "sdlc_connectors.base.httpx.Client", lambda **kw: real_client(transport=httpx.MockTransport(fake))
    )
    return fake


@pytest.fixture
def env(tmp_path, providers):
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


def test_a_token_the_provider_refuses_is_not_saved(env):
    client, *_ = env
    refused = api(client, "ada-ui", "PUT", "/api/connections/github", json={"secret": "wrong-token"})
    assert refused.status_code == 400 and refused.json()["error"] == "invalid_token"
    assert "wrong-token" not in refused.text
    assert call(client, "ada-ui", "connection_list")[0]["connections"] == []


def test_a_saved_token_is_verified_and_can_be_tested_again(env, providers):
    client, *_ = env
    saved = api(client, "ada-ui", "PUT", "/api/connections/github", json={"secret": SECRET}).json()
    assert (saved["status"], saved["account"]) == ("ok", "ada-gh")
    assert api(client, "ada-ui", "POST", "/api/connections/github/test").json() == {
        "provider": "github",
        "status": "ok",
        "account": "ada-gh",
    }
    providers.revoked = True  # the token was revoked at GitHub
    tested = api(client, "ada-ui", "POST", "/api/connections/github/test").json()
    assert tested["status"] == "refused" and tested["reason"] == "unauthorized"
    assert api(client, "ada-ui", "POST", "/api/connections/gitlab/test").status_code in (400, 404)


def test_a_token_that_cannot_be_checked_here_is_saved_as_untested(env):
    client, *_ = env
    # no team of ada's uses Jira Cloud in this configuration, so there is no site to sign in to
    saved = api(
        client, "ada-ui", "PUT", "/api/connections/jira_cloud", json={"secret": "t", "account": "ada@example.test"}
    )
    assert saved.status_code == 200 and saved.json()["status"] == "untested"
    missing = api(client, "ada-ui", "PUT", "/api/connections/jira_cloud", json={"secret": "t"})
    assert missing.json()["error"] == "account_required"


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


# Jira and repositories with the user's own connection, on their team's systems only (FR-AUTHZ-003) -------------

SYSTEMS_CONFIG = {
    **CONFIG,
    "tool_groups": {
        **CONFIG["tool_groups"],
        "connections": {
            "description": "-",
            "tools": ["connection_list", "connection_start", "connection_revoke", "connection_test"],
        },
        "jira": {
            "description": "-",
            "tools": ["team_systems", "jira_get_issue", "jira_search", "jira_create_feature", "jira_link_design"],
        },
        "repositories": {"description": "-", "tools": ["repo_list", "repo_read_file", "repo_pull_requests"]},
        "control": {
            "description": "-",
            "tools": [
                "control_publish",
                "control_status",
                "control_pull_requests",
                "feature_open",
                "feature_target_branches",
            ],
        },
    },
    "surfaces": {
        s: {
            "description": "-",
            "tool_groups": [*CONFIG["surfaces"][s]["tool_groups"], "jira", "repositories", "control"],
        }
        for s in CONFIG["surfaces"]
    },
    "teams": {**CONFIG["teams"], "risk": {"name": "Risk", "description": "-", "roles": ["member"]}},
    "grants": [
        {**CONFIG["grants"][0], "tool_groups": [*CONFIG["grants"][0]["tool_groups"], "jira", "repositories", "control"]}
    ],
    "providers": {**CONFIG["providers"], "jira_cloud": {"name": "Jira Cloud", "system": "jira", "edition": "cloud"}},
    "team_systems": {
        "payments": {
            "jira": [
                {
                    "provider": "jira_cloud",
                    "base_url": "https://pay.atlassian.net",
                    "project": "PAY",
                    "epic_type": "Epic",
                    "feature_type": "Story",
                    "story_type": "Sub-task",
                    "story_link": "parent",
                    "default": True,
                },
                {
                    "provider": "jira_cloud",
                    "base_url": "https://pay.atlassian.net",
                    "project": "CARD",
                    "epic_type": "Epic",
                    "feature_type": "Story",
                    "story_type": "Sub-task",
                    "story_link": "parent",
                    "default": False,
                },
            ],
            "confluence": [],
            "repositories": [
                {
                    "provider": "github",
                    "repo": "org/payments",
                    "design_path": "docs/specs",
                    "default_branch": "main",
                    "default": True,
                },
                {
                    "provider": "github",
                    "repo": "org/payments-gateway",
                    "design_path": "docs/specs",
                    "default_branch": "main",
                    "default": False,
                },
            ],
            "control_repo": {
                "provider": "github",
                "repo": "org/payments-sdlc-control",
                "branch": "main",
                "system_accounts": ["sdlc-bot"],
            },
        },
        "risk": {
            "jira": [],
            "confluence": [],
            "repositories": [
                {
                    "provider": "github",
                    "repo": "org/risk",
                    "design_path": "docs",
                    "default_branch": "main",
                    "default": True,
                }
            ],
        },
    },
}


FakeRepo = FakeGitHub  # sdlc_connectors.testing


class FakeJira:
    """A Jira project in memory: issues with a type, a summary, a parent and a status; JQL read just enough."""

    def __init__(self):
        self.issues: dict[str, dict] = {}
        self.next = 101
        self.created: list[dict] = []
        self.remote: dict[str, list] = {}

    def add(self, key, kind, summary, parent=None, status="To Do"):
        self.issues[key] = {"type": kind, "summary": summary, "parent": parent, "status": status}

    def json(self, key):
        i = self.issues[key]
        fields = {
            "summary": i["summary"],
            "status": {"name": i["status"]},
            "issuetype": {"name": i["type"]},
            "description": None,
        }
        return {"key": key, "fields": fields | ({"parent": {"key": i["parent"]}} if i["parent"] else {})}

    def handle(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        if path.endswith("/remotelink"):
            key = path.split("/")[-2]
            if method == "POST":
                self.remote.setdefault(key, []).append(json.loads(request.content))
                return httpx.Response(201, json={})
            return httpx.Response(200, json=self.remote.get(key, []))
        if path == "/rest/api/3/myself":
            return httpx.Response(200, json={"emailAddress": "ada@example.test"})
        if path == "/rest/api/3/field":
            return httpx.Response(200, json=[{"id": "customfield_10016", "name": "Story point estimate"}])
        if path == "/rest/api/3/search/jql":
            jql = json.loads(request.content)["jql"]
            parent = re.search(r"parent = ([A-Z]+-[0-9]+)", jql)
            kind = re.search(r'issuetype = "([^"]+)"', jql)
            words = re.search(r'text ~ "([^"]*)"', jql)
            found = [
                self.json(k)
                for k, i in self.issues.items()
                if (not parent or i["parent"] == parent.group(1))
                and (not kind or i["type"] == kind.group(1))
                and (not words or words.group(1).strip().lower() in i["summary"].lower())
                and ("statusCategory != Done" not in jql or i["status"] != "Done")
            ]
            return httpx.Response(200, json={"issues": found})
        if path == "/rest/api/3/issue" and method == "POST":
            fields = json.loads(request.content)["fields"]
            key = f"PAY-{self.next}"
            self.next += 1
            self.created.append(fields)
            self.add(key, fields["issuetype"]["name"], fields["summary"], (fields.get("parent") or {}).get("key"))
            return httpx.Response(201, json={"key": key})
        if path.startswith("/rest/api/3/issue/"):
            key = path.rsplit("/", 1)[-1]
            return httpx.Response(200, json=self.json(key)) if key in self.issues else httpx.Response(404)
        return httpx.Response(404)


@pytest.fixture
def ctrl():
    return FakeRepo("/repos/org/payments-sdlc-control")


@pytest.fixture
def target():
    return FakeRepo("/repos/org/payments")


@pytest.fixture
def jira():
    fake = FakeJira()
    fake.add("PAY-1", "Story", "PAY-1 summary")
    fake.add("PAY-2", "Sub-task", "PAY-2 summary", parent="PAY-1")
    return fake


@pytest.fixture
def senv(env, monkeypatch, ctrl, target, jira):
    """The `env` service with team systems, Ada's Jira and GitHub connections, and Jira and GitHub faked."""
    client, platform, config_root, _ = env
    publish(config_root, SYSTEMS_CONFIG)
    platform.connections.save(
        "1001", "jira_cloud", SYSTEMS_CONFIG["providers"]["jira_cloud"], "jira-token", "ada@example.test", None
    )
    platform.connections.save("1001", "github", SYSTEMS_CONFIG["providers"]["github"], "gh-token", None, None)
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        for repo in (ctrl, target):
            if path.startswith(repo.BASE + "/"):
                return repo.handle(request)
        if path.startswith("/rest/api/3/"):
            return jira.handle(request)
        return httpx.Response(404)

    real_client = REAL_CLIENT
    monkeypatch.setattr(
        "sdlc_connectors.base.httpx.Client", lambda **kw: real_client(transport=httpx.MockTransport(handler))
    )
    return client, seen


def tool(client, headers, name, **arguments):
    result = json.loads(kcall(client, headers, name, **arguments).json()["result"]["content"][0]["text"])
    return result


def test_a_feature_is_read_with_its_stories_as_the_user(senv):
    client, seen = senv
    found = tool(client, WHO["ada-ui"], "jira_get_issue", key="PAY-1")
    assert [s["key"] for s in found["stories"]] == ["PAY-2"]
    auth = seen[0].headers["authorization"].removeprefix("Basic ")
    assert base64.b64decode(auth).decode() == "ada@example.test:jira-token"
    assert 'project = "PAY" AND parent = PAY-1' in json.loads(seen[1].content)["jql"]


def test_other_projects_and_repositories_are_refused_before_any_call(senv):
    client, seen = senv
    assert tool(client, WHO["ada-ui"], "jira_get_issue", key="RISK-1")["error"] == "constraint_denied"
    assert (
        tool(client, WHO["ada-ui"], "repo_read_file", repo="org/risk", path="README.md")["error"] == "constraint_denied"
    )
    assert seen == []


def test_search_is_confined_to_the_team_project(senv):
    client, seen = senv
    tool(
        client, WHO["ada-ui"], "jira_search", text='refunds" OR project = RISK OR "', status="In Design", open_only=True
    )
    jql = json.loads(seen[0].content)["jql"]
    assert jql.startswith('project in ("PAY", "CARD") AND text ~ "refunds  OR project = RISK OR"')
    assert '"In Design"' in jql and "statusCategory != Done" in jql and len(seen) == 1


def test_a_team_lists_its_systems_with_their_defaults(senv):
    client, _ = senv
    found = tool(client, TEAM, "team_systems")["teams"]["payments"]
    assert [(j["project"], j["default"]) for j in found["jira"]] == [("PAY", True), ("CARD", False)]
    assert (found["jira"][0]["epic_type"], found["jira"][0]["feature_type"], found["jira"][0]["story_type"]) == (
        "Epic",
        "Story",
        "Sub-task",
    )
    assert [(r["repo"], r["default"]) for r in found["repositories"]] == [
        ("org/payments", True),
        ("org/payments-gateway", False),
    ]
    assert found["control_repo"] == {"repo": "org/payments-sdlc-control", "provider": "github", "branch": "main"}


def test_a_call_without_a_repository_uses_the_team_default(senv):
    client, seen = senv
    tool(client, TEAM, "repo_read_file", path="README.md")
    assert seen[0].url.path.startswith("/repos/org/payments/contents/README.md")


TEAM = {**WHO["ada-ui"], "X-SDLC-Team": "payments"}
FEATURE = {
    "epic": {"summary": "Payments 2027", "description": "-", "create": True},
    "feature": {"summary": "Refunds"},
    "stories": [{"summary": "As a payer, I want a refund"}],
}


def opened(client, summary="Refunds!"):
    """The feature the user approved in chat, opened on its branch; returns its control ID."""
    return tool(
        client, TEAM, "feature_open", content="---\napproved_by: someone-else\n---\n# Refunds\n", summary=summary
    )["control_id"]


def test_writes_need_a_run_for_the_team(senv):
    client, _ = senv
    assert tool(client, WHO["ada-ui"], "feature_open", content="# F")["error"] == "team_run_required"
    assert tool(client, WHO["ada-ui"], "jira_create_feature", control_id="F-20261126-x", **FEATURE)["error"] == (
        "team_run_required"
    )


def test_an_approved_feature_opens_its_branch_with_the_approval_written_by_the_server(senv, ctrl):
    client, _ = senv
    control_id = opened(client)
    assert re.match(r"^F-[0-9]{8}-refunds$", control_id)
    meta = yaml.safe_load(ctrl.file(f"feature/{control_id}", f"features/{control_id}/feature.md").split("---")[1])
    assert meta["approved_by"] == "ada@example.test" and meta["approved_in"] == "chat"  # not the model's front matter
    assert f"features/{control_id}/feature.md" not in ctrl.trees["main"]  # main is untouched
    status = tool(client, TEAM, "control_status", control_id=control_id)
    assert status["branch"] == f"feature/{control_id}" and status["artifacts"]["feature"]["approved"] is True
    again = tool(client, TEAM, "feature_open", content="# Refunds", summary="Refunds!")
    assert again["already_open"] and again["control_id"] == control_id  # nothing opened twice
    assert tool(client, TEAM, "control_publish", kind="feature", content="# F")["error"] == "invalid_argument"


def test_jira_gets_epic_feature_and_sub_tasks_recorded_on_the_feature_branch(senv, ctrl, jira):
    client, _ = senv
    assert tool(client, TEAM, "jira_create_feature", control_id="F-20261126-none", **FEATURE)["error"] == "not_approved"
    control_id = opened(client)
    made = tool(client, TEAM, "jira_create_feature", control_id=control_id, **FEATURE)
    assert made["epic"] == {"key": "PAY-101", "created": True}
    assert made["feature"]["key"] == "PAY-102" and made["stories"] == ["PAY-103"]
    assert jira.issues["PAY-101"]["type"] == "Epic"
    assert jira.issues["PAY-102"] | {} == {
        "type": "Story",
        "summary": "Refunds",
        "parent": "PAY-101",
        "status": "To Do",
    }
    assert jira.issues["PAY-103"]["type"] == "Sub-task" and jira.issues["PAY-103"]["parent"] == "PAY-102"
    links = yaml.safe_load(ctrl.file(f"feature/{control_id}", f"features/{control_id}/links.yaml"))
    write = links["writes"][0]
    assert write["approved_by"] == "ada@example.test" and write["results"]["epic"] == "PAY-101"
    again = tool(client, TEAM, "jira_create_feature", control_id=control_id, **FEATURE)
    assert again["error"] == "already_done"


def test_an_existing_epic_is_used_and_open_issues_are_reused(senv, jira):
    client, _ = senv
    jira.add("PAY-50", "Epic", "Payments 2027")
    jira.add("PAY-60", "Story", "Refunds")
    jira.add("PAY-61", "Sub-task", "As a payer, I want a refund", parent="PAY-60")
    control_id = opened(client)
    args = {**FEATURE, "epic": {"key": "PAY-50"}}
    made = tool(client, TEAM, "jira_create_feature", control_id=control_id, **args)
    assert made["epic"]["key"] == "PAY-50" and made["feature"]["key"] == "PAY-60" and made["stories"] == ["PAY-61"]
    assert set(made["reused"]) == {"PAY-60", "PAY-61"} and jira.created == []
    not_epic = {**FEATURE, "epic": {"key": "PAY-1"}}
    other = opened(client, summary="Cards")
    assert tool(client, TEAM, "jira_create_feature", control_id=other, **not_epic)["error"] == "invalid_argument"
    no_epic = {k: v for k, v in FEATURE.items() if k != "epic"}
    assert tool(client, TEAM, "jira_create_feature", control_id=other, **no_epic)["error"] == "invalid_argument"


def test_estimates_reach_jira_as_a_size_label_and_story_points(senv, jira):
    client, _ = senv
    control_id = opened(client)
    args = {
        **FEATURE,
        "feature": {
            "summary": "Refunds",
            "description": "Faster.",
            "estimate": "M",
            "estimate_note": "about 2-3 weeks",
        },
        "stories": [{"summary": "As a payer, I want a refund", "story_points": 5}],
    }
    tool(client, TEAM, "jira_create_feature", control_id=control_id, **args)
    epic, feature, story = jira.created
    assert feature["labels"] == ["size-M"] and "High-level estimate: M (about 2-3 weeks)" in json.dumps(
        feature["description"]
    )
    assert story["customfield_10016"] == 5 and "Story points: 5" in json.dumps(story["description"])
    wrong = {**args, "stories": [{"summary": "x", "story_points": 4}]}
    assert tool(client, TEAM, "jira_create_feature", control_id=control_id, **wrong)["error"] == "invalid_argument"


def test_the_feature_branch_opens_on_the_target_repositories(senv, ctrl, target):
    client, _ = senv
    control_id = opened(client)
    out = tool(client, TEAM, "feature_target_branches", control_id=control_id)
    assert out["repositories"] == {"org/payments": "created"} and f"feature/{control_id}" in target.trees
    again = tool(client, TEAM, "feature_target_branches", control_id=control_id)
    assert again["repositories"] == {"org/payments": "existed"}
    links = yaml.safe_load(ctrl.file(f"feature/{control_id}", f"features/{control_id}/links.yaml"))
    assert [w["action"] for w in links["writes"]] == ["open_branches", "open_branches"]
    assert tool(client, TEAM, "feature_target_branches", control_id="F-20261126-none")["error"] == "not_approved"


def test_a_design_goes_into_the_feature_branch_and_is_approved_there(senv, ctrl):
    client, _ = senv
    control_id = opened(client)
    tool(client, TEAM, "jira_create_feature", control_id=control_id, **FEATURE)
    out = tool(client, TEAM, "control_publish", kind="design", content="# Design", control_id=control_id)
    assert out["pull_request"]["base"] == f"feature/{control_id}" and ctrl.prs[1]["base"] == f"feature/{control_id}"
    twice = tool(client, TEAM, "control_publish", kind="design", content="# D2", control_id=control_id)
    assert twice["already_open"] and len(ctrl.prs) == 1
    assert tool(client, TEAM, "jira_link_design", control_id=control_id)["error"] == "not_approved"
    ctrl.merge(1, "sdlc-bot")  # a system account's merge does not approve
    assert tool(client, TEAM, "control_status", control_id=control_id)["artifacts"]["design"]["approved"] is False
    ctrl.push(f"feature/{control_id}", f"features/{control_id}/design.md", "# pushed")  # nor does a direct push
    assert tool(client, TEAM, "control_status", control_id=control_id)["artifacts"]["design"]["approved"] is False
    design = tool(client, TEAM, "control_publish", kind="design", content="# Design 3", control_id=control_id)
    ctrl.merge(design["pull_request"]["number"], "grace")
    status = tool(client, TEAM, "control_status", control_id=control_id)
    assert status["artifacts"]["design"]["approved"] and status["artifacts"]["design"]["merged_by"] == "grace"
    assert f"features/{control_id}/design.md" not in ctrl.trees["main"]  # approved on the feature branch, not main
    assert tool(client, TEAM, "jira_link_design", control_id=control_id)["feature"] == "PAY-102"
    without = tool(client, TEAM, "control_publish", kind="design", content="# D", control_id="F-20261126-none")
    assert without["error"] == "not_found"


def test_open_pull_requests_are_listed(senv, ctrl, target):
    client, _ = senv
    control_id = opened(client)
    tool(client, TEAM, "control_publish", kind="design", content="# D", control_id=control_id)
    listed = tool(client, TEAM, "control_pull_requests")
    assert [(p["control_id"], p["kind"]) for p in listed["pull_requests"]] == [(control_id, "design")]
    target.prs[9] = {"title": "Refunds", "head": "feature/x", "base": "main"}
    found = tool(client, TEAM, "repo_pull_requests")
    assert found["repo"] == "org/payments" and [p["number"] for p in found["pull_requests"]] == [9]
    assert tool(client, TEAM, "repo_pull_requests", repo="org/risk")["error"] == "constraint_denied"


def test_a_team_without_a_control_repository_cannot_open_features(senv, env):
    client, platform, config_root, _ = env
    systems = {**SYSTEMS_CONFIG["team_systems"]}
    systems["payments"] = {k: v for k, v in systems["payments"].items() if k != "control_repo"}
    publish(config_root, {**SYSTEMS_CONFIG, "team_systems": systems})
    out = tool(client, TEAM, "feature_open", content="# F")
    assert out["error"] == "constraint_denied" and "no control repository" in out["message"]


def test_without_a_connection_the_user_is_told_to_connect(senv, env):
    client, _ = senv
    env[1].connections.revoke("1001", "github")
    assert (
        tool(client, WHO["ada-ui"], "repo_read_file", repo="org/payments", path="README.md")["error"] == "not_connected"
    )


def test_connection_test_signs_in_and_never_returns_the_token(senv):
    client, _ = senv
    result = tool(client, WHO["ada-ui"], "connection_test", provider="jira_cloud")
    assert result == {"provider": "jira_cloud", "status": "ok", "account": "ada@example.test"}


# The implementation plan and the implementation with the user (DEC-0016) -----------------------------------------

IMPL_CONFIG = {
    **SYSTEMS_CONFIG,
    "tool_groups": {
        **SYSTEMS_CONFIG["tool_groups"],
        "implementation": {
            "description": "-",
            "tools": ["plan_publish", "workspace_build", "implementation_publish"],
        },
    },
    "surfaces": {
        s: {**e, "tool_groups": [*e["tool_groups"], "implementation"]} for s, e in SYSTEMS_CONFIG["surfaces"].items()
    },
    "grants": [
        {
            **SYSTEMS_CONFIG["grants"][0],
            "tool_groups": [*SYSTEMS_CONFIG["grants"][0]["tool_groups"], "implementation"],
        }
    ],
    "team_systems": {
        **SYSTEMS_CONFIG["team_systems"],
        "payments": {
            **SYSTEMS_CONFIG["team_systems"]["payments"],
            "repositories": [
                {**SYSTEMS_CONFIG["team_systems"]["payments"]["repositories"][0], "workspace": {"test": ["pytest"]}},
                SYSTEMS_CONFIG["team_systems"]["payments"]["repositories"][1],
            ],
        },
    },
}


class FakeWorkspace:
    """The credential-free job: reads the request and its archive, passes when no change writes FAIL."""

    def __init__(self):
        self.requests: list[dict] = []
        self.archives: list[dict[str, str]] = []

    async def run(self, request_path, relative):
        import io
        import tarfile

        request = json.loads(request_path.read_text(encoding="utf-8"))
        self.requests.append({**request, "relative": relative})
        with tarfile.open(fileobj=io.BytesIO((request_path.parent / request["archive"]).read_bytes())) as tar:
            files = {m.name.split("/", 1)[1]: tar.extractfile(m).read().decode() for m in tar.getmembers()}
        self.archives.append(files)
        ok = not any("FAIL" in (c.get("content") or "") for c in request["changes"])
        step = {"name": "test", "command": "pytest", "exit_code": 0 if ok else 1, "seconds": 1, "log_tail": "x"}
        (request_path.parent / "result.json").write_text(json.dumps({"ok": ok, "steps": [step]}), encoding="utf-8")


@pytest.fixture
def ienv(senv, env):
    client, _ = senv
    _, platform, config_root, store_root = env
    publish(config_root, IMPL_CONFIG)
    platform.workspace = FakeWorkspace()
    return client, platform.workspace, store_root


def designed(client, ctrl, target):
    """A feature with a design a person merged, and its branch on the target repository."""
    control_id = opened(client)
    tool(client, TEAM, "feature_target_branches", control_id=control_id)
    design = tool(client, TEAM, "control_publish", kind="design", content="# Design", control_id=control_id)
    ctrl.merge(design["pull_request"]["number"], "grace")
    target.push(f"feature/{control_id}", "app.py", "VALUE = 1\n")
    return control_id


CHANGE = [{"path": "pkg/refunds.py", "content": "def refund():\n    return 2\n"}]


def test_the_user_proposes_a_plan_only_for_a_merged_design_and_only_once(ienv, ctrl, target):
    client, _, _ = ienv
    control_id = opened(client)
    early = tool(client, TEAM, "plan_publish", control_id=control_id, repo="org/payments", content="# Plan")
    assert early["error"] == "not_approved"
    design = tool(client, TEAM, "control_publish", kind="design", content="# Design", control_id=control_id)
    ctrl.merge(design["pull_request"]["number"], "grace")
    out = tool(client, TEAM, "plan_publish", control_id=control_id, repo="org/payments", content="# Plan")
    pr = ctrl.prs[out["pull_request"]["pull_request"]]
    assert pr["head"] == f"sdlc/{control_id}/plan-payments" and pr["base"] == f"feature/{control_id}"
    assert "Published by ada@example.test" in pr["body"]
    plan = ctrl.file(f"sdlc/{control_id}/plan-payments", f"features/{control_id}/plan-payments.md")
    assert "drafted_by: ada@example.test" in plan and "merged_by: grace" in plan
    again = tool(client, TEAM, "plan_publish", control_id=control_id, repo="org/payments", content="# Plan 2")
    assert again["already_open"] is True
    other = tool(client, TEAM, "plan_publish", control_id=control_id, repo="org/risk", content="# Plan")
    assert other["error"] == "constraint_denied"  # not one of the run's team's repositories


def test_a_change_is_built_from_the_users_archive_then_opened_as_the_user(ienv, ctrl, target):
    client, workspace, store_root = ienv
    control_id = designed(client, ctrl, target)
    early = tool(client, TEAM, "workspace_build", control_id=control_id, repo="org/payments", changes=CHANGE)
    assert early["error"] == "not_approved"  # no plan merged yet
    plan = tool(client, TEAM, "plan_publish", control_id=control_id, repo="org/payments", content="# Plan")
    ctrl.merge(plan["pull_request"]["pull_request"], "grace")
    unbuilt = tool(client, TEAM, "implementation_publish", control_id=control_id, repo="org/payments", changes=CHANGE)
    assert unbuilt["error"] == "not_built"
    built = tool(client, TEAM, "workspace_build", control_id=control_id, repo="org/payments", changes=CHANGE)
    assert built["ok"] is True and built["ref"] == f"feature/{control_id}" and built["steps"][0]["exit_code"] == 0
    request = workspace.requests[0]
    assert request["relative"].startswith("artifacts/users/1001/runs/") and request["commands"] == {"test": ["pytest"]}
    assert workspace.archives[0] == {"app.py": "VALUE = 1\n"}  # fetched with Ada's connection
    assert not list(store_root.rglob("source.tar.gz"))  # the archive is not kept
    other = [{"path": "pkg/refunds.py", "content": "changed after the build"}]
    differs = tool(client, TEAM, "implementation_publish", control_id=control_id, repo="org/payments", changes=other)
    assert differs["error"] == "not_built"
    out = tool(client, TEAM, "implementation_publish", control_id=control_id, repo="org/payments", changes=CHANGE)
    number = out["pull_request"]["pull_request"]
    assert target.prs[number]["head"] == f"sdlc/{control_id}/payments"
    assert (
        target.prs[number]["base"] == f"feature/{control_id}"
        and "Implemented with ada@example.test" in (target.prs[number]["body"])
    )
    assert target.file(f"sdlc/{control_id}/payments", "pkg/refunds.py") == CHANGE[0]["content"]
    assert target.file(f"sdlc/{control_id}/payments", "app.py") == "VALUE = 1\n"
    links = yaml.safe_load(ctrl.file(f"feature/{control_id}", f"features/{control_id}/links.yaml"))
    assert [w["action"] for w in links["writes"]][-2:] == ["plan_pull_request", "implementation_pull_request"]
    rebuilt = tool(client, TEAM, "workspace_build", control_id=control_id, repo="org/payments", changes=CHANGE)
    assert rebuilt["ref"] == f"sdlc/{control_id}/payments"  # the next round starts from the pushed branch
    second = tool(client, TEAM, "implementation_publish", control_id=control_id, repo="org/payments", changes=CHANGE)
    assert second["already_open"] is True and len(target.prs) == 1


def test_a_failing_build_cannot_be_opened_and_a_repository_without_commands_needs_no_build(ienv, ctrl, target):
    client, workspace, _ = ienv
    control_id = designed(client, ctrl, target)
    plan = tool(client, TEAM, "plan_publish", control_id=control_id, repo="org/payments", content="# Plan")
    ctrl.merge(plan["pull_request"]["pull_request"], "grace")
    failing = [{"path": "pkg/refunds.py", "content": "FAIL"}]
    built = tool(client, TEAM, "workspace_build", control_id=control_id, repo="org/payments", changes=failing)
    assert built["ok"] is False
    refused = tool(client, TEAM, "implementation_publish", control_id=control_id, repo="org/payments", changes=failing)
    assert refused["error"] == "not_built" and "failed" in refused["message"]
    unsafe = tool(
        client, TEAM, "workspace_build", control_id=control_id, repo="org/payments", changes=[{"path": "../x"}]
    )
    assert unsafe["error"] == "invalid_argument" and len(workspace.requests) == 1

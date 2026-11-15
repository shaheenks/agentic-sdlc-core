"""core_mcp_gcp: the GCP stack's MCP server is sdlc_mcp with the Google parts only (CH-0022).

The user's Google ID token is verified (our OAuth clients, the configured domains), membership comes
from the configured Google groups, and anything else fails closed: missing settings stop startup,
an Entra token is refused and audited as a Google-stack rejection.
"""

import json
import logging

import pytest
from fastmcp import Client
from fastmcp.server.auth import RemoteAuthProvider
from sdlc_auth.google import GOOGLE_ISSUER, GoogleAdapter
from sdlc_auth.groups import StaticGroups
from sdlc_config import ConfigStore, load_snapshot
from sdlc_core_mcp_gcp import server as gcp
from sdlc_mcp import server as shared

from tests.mcp.test_server_library import imported_modules
from tests.support.config import GOOGLE_DOMAIN, REPO_ROOT, group_for, make_config_dir
from tests.support.entra import TEST_ENV
from tests.support.google import CLIENT_ID, FakeGoogle
from tests.support.servers import fixture_approve, fixture_review, free_port, serve

COMPONENT = REPO_ROOT / "mcp_servers" / "core_mcp_gcp" / "src" / "sdlc_core_mcp_gcp"
LEAD = f"lead@{GOOGLE_DOMAIN}"
ENV = {"SDLC_OAUTH_CLIENT_IDS": f" {CLIENT_ID} , other-client "}


def test_core_mcp_gcp_is_only_the_google_parts():
    """No server code is copied: an entry point wiring the shared Google verifier and adapter."""
    assert sorted(p.name for p in COMPONENT.glob("*.py")) == ["__init__.py", "server.py"]
    modules = imported_modules(COMPONENT / "server.py")
    assert not [m for m in modules if m.startswith(("sdlc_auth.entra", "sdlc_core_mcp."))]
    assert {"sdlc_auth.google", "sdlc_auth.groups", "sdlc_mcp"} <= modules


@pytest.fixture
def snapshot(tmp_path):
    return load_snapshot(make_config_dir(tmp_path), "local", TEST_ENV)


def test_client_ids_come_from_the_environment_and_are_required():
    assert gcp.oauth_client_ids(ENV) == [CLIENT_ID, "other-client"]
    with pytest.raises(SystemExit, match="fail closed"):
        gcp.oauth_client_ids({"SDLC_OAUTH_CLIENT_IDS": " , "})


def test_a_comment_taken_as_a_client_id_stops_startup():
    """First dev rollout (CH-0022): a trailing .env comment reached Cloud Run inside the value, and
    every token was refused for its audience. Now the server refuses to start instead."""
    value = f"{CLIENT_ID}   # web + desktop OAuth client ids, comma-separated (ID token audience)"
    with pytest.raises(SystemExit, match="malformed"):
        gcp.oauth_client_ids({"SDLC_OAUTH_CLIENT_IDS": value})


def test_domains_and_group_lookup_come_from_config(snapshot):
    auth = gcp.build_auth(snapshot, "http://127.0.0.1:1", environ=ENV)
    verifier = auth.token_verifier
    assert verifier.allowed_domains == (GOOGLE_DOMAIN,)
    assert sorted(verifier.audience) == sorted([CLIENT_ID, "other-client"])
    assert verifier.issuer == GOOGLE_ISSUER
    adapter = gcp.build_identity(snapshot, StaticGroups({}), environ=ENV)
    assert isinstance(adapter, GoogleAdapter) and adapter.name == "google"


def test_no_identity_google_stops_startup(tmp_path):
    config_dir = make_config_dir(tmp_path)
    for path in [config_dir / "roles.yaml", *(config_dir / "teams").glob("*.yaml")]:
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(x for x in lines if " group: " not in x) + "\n", encoding="utf-8")
    platform = config_dir / "platform.yaml"
    lines = platform.read_text(encoding="utf-8").splitlines()
    kept = [x for x in lines if not x.startswith("  google:")]
    platform.write_text("\n".join(kept) + "\n", encoding="utf-8")
    snap = load_snapshot(config_dir, "local", TEST_ENV)
    assert snap.platform.google is None
    with pytest.raises(SystemExit, match="identity.google"):
        gcp.build_auth(snap, "http://127.0.0.1:1", environ=ENV)
    with pytest.raises(SystemExit, match="identity.google"):
        gcp.build_identity(snap, StaticGroups({}), environ=ENV)


@pytest.fixture
def google() -> FakeGoogle:
    return FakeGoogle()


@pytest.fixture
def gcp_url(tmp_path, google):
    """core_mcp_gcp wired as in main(), with the fake issuer's keys and a static group directory."""
    config_dir = make_config_dir(tmp_path)
    store = ConfigStore(lambda: load_snapshot(config_dir, "local", TEST_ENV))
    port = free_port()
    groups = StaticGroups(
        {LEAD: [group_for("SDLC.User"), group_for("SDLC.Payments.Approver"), "other@else.test"]}
    )
    adapter = gcp.build_identity(store.current(), groups, environ=ENV)
    auth = RemoteAuthProvider(
        token_verifier=google.verifier(),
        authorization_servers=[GOOGLE_ISSUER],
        base_url=f"http://127.0.0.1:{port}",
        resource_name=gcp.NAME,
    )
    server = shared.build_server(store, auth, identity=adapter, name=gcp.NAME)
    for fn in (fixture_review, fixture_approve):  # fixture-only catalog tools (CH-0003)
        server.tool(fn)
    with serve(shared.build_http_app(server, store, adapter), port) as url:
        yield url


async def test_a_google_user_gets_the_roles_of_their_groups(gcp_url, google):
    async with Client(f"{gcp_url}/mcp", auth=google.token(email=LEAD, sub="1" * 21)) as client:
        who = (await client.call_tool("whoami", {"explain": True})).data
    assert who["sub"] == "1" * 21 and who["email"] == LEAD and who["domain"] == GOOGLE_DOMAIN
    policy = who["policy"]
    assert "approver@payments" in json.dumps(policy) and "viewer" in json.dumps(policy)
    assert "other@else.test" not in json.dumps(policy)  # only groups the config binds


async def test_a_google_user_in_no_group_gets_signed_in_basics_only(gcp_url, google):
    async with Client(f"{gcp_url}/mcp", auth=google.token(email=f"new@{GOOGLE_DOMAIN}")) as client:
        tools = {t.name for t in await client.list_tools()}
    assert tools == {"ping", "whoami"}


async def test_an_entra_token_is_refused_and_audited_as_google(gcp_url, entra, caplog):
    caplog.set_level(logging.INFO, logger="sdlc.audit")
    with pytest.raises(Exception):  # noqa: B017 (the client reports the 401 generically)
        async with Client(f"{gcp_url}/mcp", auth=entra.token()) as client:
            await client.call_tool("whoami", {})
    records = [json.loads(r.message) for r in caplog.records if r.name == "sdlc.audit"]
    failures = [r for r in records if r.get("event") == "auth_failure"]
    assert failures and all(r["idp"] == "google" for r in failures)
    assert {r["reason"] for r in failures} == {"wrong_issuer"}


async def test_tool_calls_record_the_stack(gcp_url, google, caplog):
    caplog.set_level(logging.INFO, logger="sdlc.audit")
    async with Client(f"{gcp_url}/mcp", auth=google.token(email=LEAD)) as client:
        await client.call_tool("ping", {})
    calls = [json.loads(r.message) for r in caplog.records if r.name == "sdlc.audit"]
    calls = [r for r in calls if r.get("event") == "tool_call" and r.get("tool") == "ping"]
    assert calls and calls[-1]["idp"] == "google" and calls[-1]["upn"] == LEAD


# --- the deployed environment has no ENTRA_* (first dev rollout failed on it, CH-0022) --------

GCP_ENV = {"SDLC_IDENTITY_PROVIDER": "google", **ENV}


def test_the_config_loads_on_the_gcp_stack_without_entra_settings(tmp_path):
    """platform.yaml names ${ENTRA_*} for the Entra stack; the GCP stack never reads them."""
    from sdlc_config import ConfigError
    from sdlc_config.loader import DUMMY_ENV_VALUE

    config_dir = make_config_dir(tmp_path)
    snap = load_snapshot(config_dir, "local", GCP_ENV)
    assert snap.platform.tenant_id == DUMMY_ENV_VALUE  # inert: no Entra verifier on this stack
    assert snap.platform.google.allowed_domains == (GOOGLE_DOMAIN,)
    gcp.build_auth(snap, "http://127.0.0.1:1", environ=GCP_ENV)
    with pytest.raises(ConfigError, match="ENTRA_TENANT_ID is not set"):
        load_snapshot(config_dir, "local", ENV)  # the Entra stack still fails closed


def test_only_entra_settings_are_optional_on_the_gcp_stack(tmp_path):
    from sdlc_config import ConfigError

    config_dir = make_config_dir(tmp_path)
    platform = config_dir / "platform.yaml"
    text = platform.read_text(encoding="utf-8")
    platform.write_text(text.replace("[access_as_user]", '["${SDLC_OTHER}"]'), encoding="utf-8")
    with pytest.raises(ConfigError, match="SDLC_OTHER is not set"):
        load_snapshot(config_dir, "local", GCP_ENV)


def test_the_server_declares_its_stack(monkeypatch):
    seen = {}
    monkeypatch.setenv("SDLC_IDENTITY_PROVIDER", "")  # restored to its state before the test
    monkeypatch.delenv("SDLC_IDENTITY_PROVIDER")
    monkeypatch.setattr(gcp.shared, "serve", lambda *a, **k: seen.update(env=dict(gcp.os.environ)))
    gcp.main()
    assert seen["env"]["SDLC_IDENTITY_PROVIDER"] == "google"

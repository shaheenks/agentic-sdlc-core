"""M8: Agent Engine sessions on GCP (full resource name only, retention TTL on every session)."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from google.adk.cli.service_registry import get_service_registry
from google.adk.cli.utils.service_factory import create_session_service_from_options
from sdlc_web.sessions import (
    SCHEME,
    RetainedVertexAiSessionService,
    parse_agent_engine_uri,
    register_agent_engine_sessions,
)

ENGINE = "projects/sdlc-demo/locations/asia-southeast1/reasoningEngines/1234567890"
URI = f"agentengine://{ENGINE}"


@pytest.fixture
def registry():
    """ADK's process-wide registry, restored after the test."""
    reg = get_service_registry()
    saved = reg._session_factories.get(SCHEME)
    yield reg
    reg._session_factories[SCHEME] = saved


class FakeSessions:
    def __init__(self):
        self.calls = []

    async def create(self, *, name, user_id, config):
        self.calls.append({"name": name, "user_id": user_id, "config": config})
        response = SimpleNamespace(
            name=f"{name}/sessions/42",
            update_time=datetime.now(UTC),
            session_state=config.get("session_state"),
        )
        return SimpleNamespace(response=response)


class FakeClient:
    def __init__(self, sessions):
        self.agent_engines = SimpleNamespace(sessions=sessions)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def service_with_fake(ttl_seconds=7 * 86400):
    svc = RetainedVertexAiSessionService(
        project="sdlc-demo",
        location="asia-southeast1",
        agent_engine_id="1234567890",
        ttl_seconds=ttl_seconds,
    )
    fake = FakeSessions()
    svc._get_api_client = lambda: FakeClient(fake)
    return svc, fake


def test_parse_accepts_only_the_full_resource_name():
    assert parse_agent_engine_uri(URI) == ("sdlc-demo", "asia-southeast1", "1234567890")
    for bad in (
        "agentengine://1234567890",  # short id: location would come from the model's `global`
        "agentengine://projects/p/locations/l/reasoningEngines/abc",
        "agentengine://projects/p/locations/l/reasoningEngines/1/sessions/2",
        f"sqlite://{ENGINE}",
    ):
        with pytest.raises(ValueError):
            parse_agent_engine_uri(bad)


def test_every_new_session_gets_the_retention_ttl():
    svc, fake = service_with_fake()
    session = asyncio.run(
        svc.create_session(app_name="bootstrap", user_id="oid-1", state={"k": "v"})
    )
    call = fake.calls[0]
    assert call["name"] == "reasoningEngines/1234567890"
    assert call["user_id"] == "oid-1"
    assert call["config"]["ttl"] == "604800s"
    assert call["config"]["session_state"] == {"k": "v"}
    assert (session.id, session.user_id) == ("42", "oid-1")


def test_an_explicit_expiry_is_kept():
    svc, fake = service_with_fake()
    asyncio.run(
        svc.create_session(app_name="bootstrap", user_id="u", expire_time="2026-12-01T00:00:00Z")
    )
    assert "ttl" not in fake.calls[0]["config"]


def test_retention_must_be_positive():
    with pytest.raises(ValueError):
        service_with_fake(ttl_seconds=0)


def test_registered_factory_serves_adk_web_and_agui(registry, tmp_path):
    register_agent_engine_sessions(retention_days=2)
    # adk web (get_fast_api_app) and /agui (mount_agui) both build their store this way
    svc = create_session_service_from_options(
        base_dir=tmp_path, session_service_uri=URI, use_local_storage=False
    )
    assert isinstance(svc, RetainedVertexAiSessionService)
    assert svc.ttl_seconds == 2 * 86400
    assert (svc._project, svc._location, svc._agent_engine_id) == (
        "sdlc-demo",
        "asia-southeast1",
        "1234567890",
    )
    with pytest.raises(ValueError):
        create_session_service_from_options(
            base_dir=tmp_path, session_service_uri="agentengine://123", use_local_storage=False
        )

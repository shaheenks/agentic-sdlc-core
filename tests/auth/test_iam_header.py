"""The agent's MCP headers on GCP-native hosting (CH-0014, design D17 N5): the user's Entra token in
Authorization as always, plus the agent's own Google ID token in X-Serverless-Authorization for
Cloud Run IAM, only when SDLC_MCP_IAM_AUDIENCE is set and only alongside a user token."""

import pytest
from sdlc_auth import adk
from sdlc_auth.adk import (
    AGENT_SESSION_HEADER,
    IAM_AUDIENCE_ENV,
    IAM_HEADER,
    agent_header_provider,
    reset_request_token,
    set_request_token,
)

AUDIENCE = "https://sdlc-mcp-native-123.asia-southeast1.run.app"


class _Session:
    id = "conv-1"


class _Ctx:
    state: dict = {}
    session = _Session()


@pytest.fixture
def fetched(monkeypatch):
    calls = []

    def fake_fetch(audience):
        calls.append(audience)
        return f"google-id-token-{len(calls)}"

    monkeypatch.setattr(adk, "_id_tokens", adk._IdTokenCache(fetch=fake_fetch))
    return calls


def headers_for(token):
    bound = set_request_token(token)
    try:
        return agent_header_provider(_Ctx())
    finally:
        reset_request_token(bound)


def test_off_by_default(monkeypatch, fetched):
    monkeypatch.delenv(IAM_AUDIENCE_ENV, raising=False)
    assert headers_for("user-token") == {
        "Authorization": "Bearer user-token",
        AGENT_SESSION_HEADER: "conv-1",
    }
    assert fetched == []


def test_adds_the_agent_id_token_next_to_the_user_token(monkeypatch, fetched):
    monkeypatch.setenv(IAM_AUDIENCE_ENV, AUDIENCE)
    headers = headers_for("user-token")
    assert headers["Authorization"] == "Bearer user-token"  # never replaced by the Google token
    assert headers[IAM_HEADER] == "Bearer google-id-token-1"
    assert fetched == [AUDIENCE]
    headers_for("other-user")  # cached per audience: one fetch per process and hour
    assert fetched == [AUDIENCE]


def test_no_user_token_no_headers_at_all(monkeypatch, fetched):
    """The agent never calls the MCP server on its own behalf."""
    monkeypatch.setenv(IAM_AUDIENCE_ENV, AUDIENCE)
    assert agent_header_provider(_Ctx()) == {}
    assert fetched == []


def test_token_is_refreshed_before_it_expires(monkeypatch, fetched):
    monkeypatch.setenv(IAM_AUDIENCE_ENV, AUDIENCE)
    clock = iter([0.0, 46 * 60.0, 46 * 60.0])  # stored at 0; checked and re-stored 46 min later
    monkeypatch.setattr(adk.time, "monotonic", lambda: next(clock))
    assert headers_for("t")[IAM_HEADER] == "Bearer google-id-token-1"
    assert headers_for("t")[IAM_HEADER] == "Bearer google-id-token-2"


def test_every_mcp_client_uses_one_helper(monkeypatch, fetched):
    """mcp_headers backs the toolset header provider, team context and Goldfish (CH-0014 fix: the
    team-context client had sent the Entra token alone and was refused by Cloud Run IAM)."""
    from sdlc_agent import goldfish, team_context

    monkeypatch.setenv(IAM_AUDIENCE_ENV, AUDIENCE)
    headers = adk.mcp_headers("user-token", "conv-9")
    assert headers == {
        "Authorization": "Bearer user-token",
        AGENT_SESSION_HEADER: "conv-9",
        IAM_HEADER: "Bearer google-id-token-1",
    }
    assert adk.mcp_headers(None) == {}
    assert team_context.mcp_headers is adk.mcp_headers
    assert goldfish.mcp_headers is adk.mcp_headers


def test_mcp_timeout(monkeypatch):
    monkeypatch.delenv("SDLC_MCP_TIMEOUT", raising=False)
    assert adk.mcp_timeout_seconds() == 30.0
    monkeypatch.setenv("SDLC_MCP_TIMEOUT", "12")
    assert adk.mcp_timeout_seconds() == 12.0

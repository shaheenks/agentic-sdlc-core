"""Correlation IDs on audit records: mcp_session_id and agent_session_id (tracking only)."""

import json

import httpx
import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from sdlc_auth.adk import (
    AGENT_SESSION_HEADER,
    agent_header_provider,
    reset_request_token,
    set_request_token,
)

from tests.support.entra import G_ENG_ALL, G_PAYMENTS_DEVS


def audit(caplog) -> list[dict]:
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == "sdlc.audit"]


def agent_client(base_url, token, conversation: str | None) -> Client:
    headers = {AGENT_SESSION_HEADER: conversation} if conversation else {}
    return Client(StreamableHttpTransport(f"{base_url}/mcp", headers=headers, auth=token))


class _Ctx:
    def __init__(self, sid):
        self.session = type("S", (), {"id": sid})()
        self.state = {}


def test_agent_header_provider_adds_conversation_id_only_with_a_token():
    assert agent_header_provider(_Ctx("conv-1")) == {}  # no user token: nothing at all
    reset = set_request_token("tok")
    try:
        assert agent_header_provider(_Ctx("conv-1")) == {
            "Authorization": "Bearer tok",
            AGENT_SESSION_HEADER: "conv-1",
        }
        assert agent_header_provider(_Ctx(None)) == {"Authorization": "Bearer tok"}
    finally:
        reset_request_token(reset)


async def test_every_event_carries_both_session_ids(base_url, entra, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    token = entra.token(groups=[G_ENG_ALL, G_PAYMENTS_DEVS])
    async with agent_client(base_url, token, "e7a1c0de-conv-0001") as c:
        await c.list_tools()
        await c.call_tool("list_skills", {})
        await c.call_tool("load_skill", {"name": "pci-checklist"})
    records = audit(caplog)
    assert {r["event"] for r in records} == {
        "tools_list",
        "tool_call",
        "skills_list",
        "skill_access",
    }
    assert {r["agent_session_id"] for r in records} == {"e7a1c0de-conv-0001"}
    # current MCP protocol: stateless server, no Mcp-Session-Id header -> not recorded
    assert {r["mcp_session_id"] for r in records} == {None}
    # request_id still distinguishes the individual requests
    assert len({r["request_id"] for r in records if r["event"] == "tool_call"}) == 2


def test_mcp_session_header_is_recorded_when_a_client_sends_it(base_url, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    httpx.post(
        f"{base_url}/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": "legacy-session-42",
        },
    )
    [failure] = [r for r in audit(caplog) if r["event"] == "auth_failure"]
    assert failure["mcp_session_id"] == "legacy-session-42"


async def test_two_conversations_are_separated(base_url, entra, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    token = entra.token(groups=[G_ENG_ALL])
    for conversation in ("conv-a", "conv-b"):
        async with agent_client(base_url, token, conversation) as c:
            await c.call_tool("whoami", {})
    calls = [r for r in audit(caplog) if r["event"] == "tool_call"]
    assert [r["agent_session_id"] for r in calls] == ["conv-a", "conv-b"]


@pytest.mark.parametrize("bad", ["x" * 200, "conv id with spaces", 'conv"},{"forged":1'])
async def test_malformed_conversation_ids_are_not_logged_verbatim(base_url, entra, caplog, bad):
    caplog.set_level("INFO", logger="sdlc.audit")
    async with agent_client(base_url, entra.token(groups=[G_ENG_ALL]), bad) as c:
        await c.call_tool("whoami", {})
    [call] = [r for r in audit(caplog) if r["event"] == "tool_call"]
    assert call["agent_session_id"] == "invalid"


async def test_missing_conversation_id_is_null(base_url, entra, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    async with agent_client(base_url, entra.token(groups=[G_ENG_ALL]), None) as c:
        await c.call_tool("whoami", {})
    [call] = [r for r in audit(caplog) if r["event"] == "tool_call"]
    assert call["agent_session_id"] is None


def test_auth_failures_carry_the_conversation_id(base_url, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    httpx.post(
        f"{base_url}/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={
            "Accept": "application/json, text/event-stream",
            AGENT_SESSION_HEADER: "conv-expired-token",
        },
    )
    [failure] = [r for r in audit(caplog) if r["event"] == "auth_failure"]
    assert failure["agent_session_id"] == "conv-expired-token"

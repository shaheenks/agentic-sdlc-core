"""The agent's McpToolset forwards the request's user token to the MCP server (no LLM needed)."""

import pytest
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from sdlc_auth.adk import (
    USER_TOKEN_STATE_KEY,
    bearer_header_provider,
    get_user_token,
    reset_request_token,
    set_request_token,
)


def toolset(base_url: str) -> McpToolset:
    # Same construction as agents/bootstrap/agent.py
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=f"{base_url}/mcp"),
        header_provider=bearer_header_provider,
    )


class _Ctx:
    """Stand-in for ADK's ReadonlyContext (ADK only calls header_provider when one is passed)."""

    def __init__(self, state=None):
        self.state = state or {}


def test_get_user_token_sources():
    assert get_user_token(None) is None
    assert get_user_token(_Ctx({USER_TOKEN_STATE_KEY: "from-state"})) == "from-state"
    reset = set_request_token("from-request")
    try:  # the validated request token wins over session state
        assert get_user_token(_Ctx({USER_TOKEN_STATE_KEY: "from-state"})) == "from-request"
        assert bearer_header_provider(None) == {"Authorization": "Bearer from-request"}
    finally:
        reset_request_token(reset)
    assert bearer_header_provider(None) == {}


async def test_toolset_lists_tools_with_user_token(base_url, entra):
    ts = toolset(base_url)
    reset = set_request_token(entra.token())
    try:
        names = {t.name for t in await ts.get_tools(_Ctx())}
    finally:
        reset_request_token(reset)
        await ts.close()
    assert {"whoami", "list_skills", "load_skill"} <= names


async def test_toolset_without_user_token_is_rejected(base_url):
    ts = toolset(base_url)
    try:
        with pytest.raises(Exception):  # noqa: B017 (ADK wraps the 401 in a generic error)
            await ts.get_tools(_Ctx())
    finally:
        await ts.close()


async def test_each_user_gets_own_mcp_session(base_url, entra):
    """ADK pools MCP sessions per header set, so two users never share a session."""
    ts = toolset(base_url)
    manager = ts._mcp_session_manager
    try:
        keys = []
        for oid in ("aaaaaaaa-0000-0000-0000-000000000001", "bbbbbbbb-0000-0000-0000-000000000002"):
            reset = set_request_token(entra.token(oid=oid))
            try:
                assert await ts.get_tools(_Ctx())
                keys.append(manager._session_key_for(bearer_header_provider(None)))
            finally:
                reset_request_token(reset)
        assert len(set(keys)) == 2
        assert set(keys) <= set(manager._session_contexts)
    finally:
        await ts.close()

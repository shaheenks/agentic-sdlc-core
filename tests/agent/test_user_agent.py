"""user_agent forwards the user's token and nothing else (NFR-SEC-006, NFR-REL-002, CH-0006).

Offline: imports agents/user_agent/agent.py (building an ADK Agent needs no model call) and runs
its MCP header provider against a stand-in ADK context.
"""

import importlib.util
from pathlib import Path

import pytest
from google.adk.tools.mcp_tool import McpToolset
from sdlc_auth.adk import (
    AGENT_SESSION_HEADER,
    USER_TOKEN_STATE_KEY,
    agent_header_provider,
    reset_request_token,
    set_request_token,
)

AGENT_FILE = Path(__file__).resolve().parents[2] / "agents" / "user_agent" / "agent.py"


@pytest.fixture(scope="module")
def toolset() -> McpToolset:
    spec = importlib.util.spec_from_file_location("user_agent_under_test", AGENT_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    toolsets = [t for t in module.root_agent.tools if isinstance(t, McpToolset)]
    assert len(toolsets) == 1
    return toolsets[0]


class _Session:
    def __init__(self, session_id):
        self.id = session_id


class _Ctx:
    """Stand-in for ADK's ReadonlyContext: session state and the session."""

    def __init__(self, token=None, session_id=None):
        self.state = {USER_TOKEN_STATE_KEY: token} if token else {}
        self.session = _Session(session_id)


def test_mcp_toolset_uses_the_user_header_provider(toolset):
    assert toolset._header_provider is agent_header_provider


def test_headers_carry_exactly_the_user_token_and_conversation(toolset):
    headers = toolset._header_provider(_Ctx(token="user-token", session_id="conv-1"))
    assert headers == {"Authorization": "Bearer user-token", AGENT_SESSION_HEADER: "conv-1"}


def test_request_token_is_forwarded(toolset):
    reset = set_request_token("request-token")
    try:
        headers = toolset._header_provider(_Ctx(session_id="conv-2"))
    finally:
        reset_request_token(reset)
    assert headers == {"Authorization": "Bearer request-token", AGENT_SESSION_HEADER: "conv-2"}


def test_no_user_token_sends_no_authorization(toolset):
    """No service-token fallback: without a user token the MCP server answers 401."""
    assert toolset._header_provider(_Ctx(session_id="conv-3")) == {}
    assert toolset._header_provider(None) == {}

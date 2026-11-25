"""user_agent (FR-AGT-005, FR-WFL-009, FR-AUTHZ-008; DEC-0010): headers to user_agent_mcp, the runtime
application's guards, and the local server in Agent Runtime's request shape. The model is a fake."""

import asyncio
import json
from collections.abc import AsyncGenerator

import pytest
from google.adk.agents import Agent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from starlette.testclient import TestClient
from user_agent.__main__ import create_server
from user_agent.agent import title_from_first_message
from user_agent.identity import EMAIL_KEY, IdTokens, mcp_headers, tokens_from_env
from user_agent.runtime import Refused, UserAgentApp


class FakeLlm(BaseLlm):
    model: str = "fake"

    async def generate_content_async(self, llm_request, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        asked = llm_request.contents[-1].parts[0].text
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=f"echo: {asked}")]))


def app() -> UserAgentApp:
    agent = Agent(name="user_agent", model=FakeLlm(), instruction="-", before_agent_callback=title_from_first_message)
    return UserAgentApp(agent=agent)


def run(coro):
    return asyncio.run(coro)


async def collect(stream):
    return [e async for e in stream]


def test_headers_carry_the_session_user_and_the_runtime_proof():
    tokens = IdTokens("https://mcp.example.test/mcp", fetch=lambda aud: f"id-token-for:{aud}")
    headers = mcp_headers("1001", {EMAIL_KEY: "ada@example.test", "sdlc_team": "payments"}, tokens)
    assert headers == {
        "X-SDLC-User-Id": "1001",
        "X-SDLC-User-Email": "ada@example.test",
        "X-SDLC-Surface": "user_agent",
        "X-SDLC-Team": "payments",
        "Authorization": "Bearer id-token-for:https://mcp.example.test/mcp",
    }


@pytest.mark.parametrize(
    ("user_id", "state"), [(None, {EMAIL_KEY: "a@x.test"}), ("1001", {}), ("1001", {EMAIL_KEY: ""})]
)
def test_no_user_means_no_headers_so_the_mcp_server_refuses(user_id, state):
    assert mcp_headers(user_id, state, IdTokens("a", fetch=lambda aud: "t")) == {}


def test_id_tokens_are_cached():
    calls = []
    tokens = IdTokens("aud", fetch=lambda aud: calls.append(aud) or "t")
    assert tokens.get() == tokens.get() == "t" and calls == ["aud"]


def test_caller_auth_setting():
    assert tokens_from_env("https://m/mcp", {"SDLC_CALLER_AUTH": "none"}) is None
    assert tokens_from_env("https://m/mcp", {}).audience == "https://m/mcp"
    with pytest.raises(ValueError):
        tokens_from_env("https://m/mcp", {"SDLC_CALLER_AUTH": "magic"})


def test_a_session_needs_the_email_and_only_known_state():
    a = app()
    with pytest.raises(Refused):
        run(a.async_create_session(user_id="1001", state={}))
    with pytest.raises(Refused):
        run(a.async_create_session(user_id="1001", state={EMAIL_KEY: "a@x.test", "sdlc_admin": True}))


def test_a_query_runs_only_in_the_users_own_session():
    a = app()
    session = run(a.async_create_session(user_id="1001", state={EMAIL_KEY: "ada@example.test"}))
    events = run(collect(a.async_stream_query(message="hello", user_id="1001", session_id=session["id"])))
    assert any("echo: hello" in json.dumps(e) for e in events)
    stored = run(a.async_get_session(user_id="1001", session_id=session["id"]))
    assert stored.state["sdlc_title"] == "hello"  # the first message names the chat
    with pytest.raises(RuntimeError, match="Session not found"):  # another user naming the session
        run(collect(a.async_stream_query(message="x", user_id="1002", session_id=session["id"])))
    with pytest.raises(Refused):
        run(collect(a.async_stream_query(message="x", user_id="1001")))
    with pytest.raises(Refused):
        run(collect(a.async_stream_query(message="x", user_id="1001", session_id=session["id"], session_events=[{}])))


def test_sessions_are_listed_per_user():
    a = app()
    run(a.async_create_session(user_id="1001", state={EMAIL_KEY: "ada@example.test", "sdlc_title": "Refunds"}))
    run(a.async_create_session(user_id="1002", state={EMAIL_KEY: "grace@example.test"}))
    listed = run(a.async_list_sessions(user_id="1001"))
    assert [s.state.get("sdlc_title") for s in listed.sessions] == ["Refunds"]


def test_only_the_needed_operations_are_offered():
    assert app().register_operations() == {
        "async": ["async_create_session", "async_get_session", "async_list_sessions", "async_delete_session"],
        "async_stream": ["async_stream_query"],
    }


def test_local_server_speaks_agent_runtimes_shape():
    client = TestClient(create_server(app()))
    created = client.post(
        "/v1/local:query",
        json={"class_method": "async_create_session", "input": {"user_id": "1001", "state": {EMAIL_KEY: "a@x.test"}}},
    )
    session_id = created.json()["output"]["id"]
    body = {
        "class_method": "async_stream_query",
        "input": {"user_id": "1001", "session_id": session_id, "message": "hi"},
    }
    streamed = client.post("/v1/local:streamQuery?alt=sse", json=body).text
    assert streamed.startswith("data: ") and "echo: hi" in streamed
    other = client.post(
        "/v1/local:query",
        json={"class_method": "async_get_session", "input": {"user_id": "1002", "session_id": session_id}},
    )
    assert other.status_code == 400
    assert client.post("/v1/local:query", json={"class_method": "async_search_memory", "input": {}}).status_code == 400

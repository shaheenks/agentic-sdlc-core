"""version-01 M5 spike: the AG-UI endpoint (/agui, ag_ui_adk) behind the Entra middleware.

A scripted test agent (tests/support/agui_agents/probe) calls one tool that records what it sees,
so a real AG-UI run is checked end to end without an LLM:
  - the user's token reaches tool calls through the request ContextVar (the run task inherits it);
  - the user id is the token's oid, whatever the client sends;
  - client state never carries tokens or temp:/app:/user: keys;
  - another user cannot read a thread's history through /agents/state.
"""

import json
from pathlib import Path

import httpx
import pytest
from sdlc_auth.adk import USER_TOKEN_STATE_KEY
from sdlc_web.app import create_app

from tests.support.agui_records import RECORDS

AGENTS_DIR = Path(__file__).resolve().parents[1] / "support" / "agui_agents"
OID_A = "aaaaaaaa-0000-0000-0000-00000000000a"
OID_B = "bbbbbbbb-0000-0000-0000-00000000000b"


@pytest.fixture
def web(entra):
    RECORDS.clear()
    app = create_app(AGENTS_DIR, entra.verifier(), host="127.0.0.1", port=8000, agui_agent="probe")
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://agent")


def run_input(thread: str, text: str, state: dict | None = None, **extra) -> dict:
    return {
        "threadId": thread,
        "runId": f"run-{thread}-{len(text)}",
        "messages": [{"id": f"m-{len(text)}", "role": "user", "content": text}],
        "tools": [],
        "context": [],
        "state": state or {},
        "forwardedProps": {},
        **extra,
    }


async def run(web, token: str, payload: dict) -> list[dict]:
    resp = await web.post(
        "/agui",
        json=payload,
        headers={"X-Forwarded-Access-Token": token, "Accept": "text/event-stream"},
    )
    assert resp.status_code == 200, resp.text
    events = []
    for line in resp.text.splitlines():
        if line.startswith("data:"):
            events.append(json.loads(line[len("data:") :]))
    return events


async def test_agui_needs_sign_in(web):
    resp = await web.post("/agui", json=run_input("t0", "hi"))
    assert resp.status_code == 401
    assert (await web.post("/agents/state", json={"threadId": "t0"})).status_code == 401


async def test_tool_calls_see_the_users_token_and_oid(web, entra):
    token = entra.token(oid=OID_A)
    payload = run_input(
        "t1",
        "hello",
        state={
            USER_TOKEN_STATE_KEY: "forged-token",
            "temp:other": "x",
            "user:pref": "x",
            "app:flag": "x",
            "theme": "dark",
        },
        userId=OID_B,  # ignored: the user is the token's oid
    )
    events = await run(web, token, payload)
    kinds = [e.get("type") for e in events]
    assert "RUN_FINISHED" in kinds and "RUN_ERROR" not in kinds, kinds
    assert "probe done" in "".join(e.get("delta", "") for e in events)
    [seen] = RECORDS
    assert seen["token"] == token  # ContextVar inherited by the run task
    assert seen["oid"] == OID_A and seen["session_user"] == OID_A
    assert "theme" in seen["state_keys"]
    assert not any(k.startswith(("temp:", "user:", "app:")) for k in seen["state_keys"])


async def test_persisted_state_has_no_token_and_threads_are_per_user(web, entra):
    token_a, token_b = entra.token(oid=OID_A), entra.token(oid=OID_B)
    await run(web, token_a, run_input("shared-thread", "secret question from A"))

    resp = await web.post(
        "/agents/state",
        json={"threadId": "shared-thread", "userId": OID_A, "appName": "probe"},
        headers={"X-Forwarded-Access-Token": token_a},
    )
    assert resp.status_code == 200, resp.text
    assert "secret question from A" in resp.text  # the owner sees their history
    assert token_a not in resp.text and "forged" not in resp.text

    # B asks for the same thread id, even naming A: B never gets A's conversation
    resp = await web.post(
        "/agents/state",
        json={"threadId": "shared-thread", "userId": OID_A, "appName": "probe"},
        headers={"X-Forwarded-Access-Token": token_b},
    )
    assert "secret question from A" not in resp.text

    # B running on the same thread id gets B's own session
    await run(web, token_b, run_input("shared-thread", "question from B"))
    assert RECORDS[-1]["session_user"] == OID_B and RECORDS[-1]["token"] == token_b


async def test_agui_is_off_unless_an_agent_is_named(entra):
    app = create_app(AGENTS_DIR, entra.verifier(), host="127.0.0.1", port=8000)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://agent")
    resp = await client.post(
        "/agui",
        json=run_input("t", "hi"),
        headers={"X-Forwarded-Access-Token": entra.token(oid=OID_A)},
    )
    assert resp.status_code in (404, 405)

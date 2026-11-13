"""The user agent's Agent Runtime entry point (CH-0014): token check, oid binding, session
ownership, state cleaning, and the user token bound only for the call.

Offline: a stand-in agent reports what it sees (no model), sessions are in memory, tokens come
from the fake Entra issuer.
"""

import sys
from pathlib import Path

import pytest
from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.sessions import InMemorySessionService
from google.genai import types
from sdlc_agent.runtime_guard import clean_state
from sdlc_auth.adk import USER_TOKEN_STATE_KEY, get_user_token

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agents"))
from user_agent.runtime_app import TITLE_STATE_KEY, UserAgentApp  # noqa: E402

ALICE = "aaaaaaaa-0000-0000-0000-00000000000a"
BOB = "bbbbbbbb-0000-0000-0000-00000000000b"


class Echo(BaseAgent):
    """Answers with the user id and whether the user's token is bound during the run."""

    async def _run_async_impl(self, ctx):
        token = get_user_token()
        text = f"user={ctx.session.user_id} token={'yes' if token else 'no'}"
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(role="model", parts=[types.Part(text=text)]),
        )


@pytest.fixture
def app(entra):
    sessions = InMemorySessionService()
    a = UserAgentApp(verifier=entra.verifier(), agent=Echo(name="echo"), session_service=sessions)
    a.set_up()
    a.sessions = sessions
    return a


async def run(app, token, message="hello", **kw):
    return [e async for e in app.stream_query(message=message, user_token=token, **kw)]


def texts(events):
    return [p["text"] for e in events if "content" in e for p in e["content"]["parts"]]


async def test_streams_as_the_token_user_with_the_token_bound(app, entra):
    events = await run(app, entra.token(oid=ALICE))
    assert "session" in events[0]
    assert texts(events) == [f"user={ALICE} token=yes"]
    assert get_user_token() is None  # unbound after the call


def error_code(result):
    """The code of an error result (CH-0019: refusals are results, never exceptions)."""
    if isinstance(result, list):
        assert len(result) == 1, result  # a refused stream is a single event, no session
        result = result[0]
    return result["error"]["code"]


@pytest.mark.parametrize("token", [None, "", "not.a.jwt"])
async def test_no_valid_token_no_answer(app, token):
    assert error_code(await run(app, token)) == "unauthenticated"


async def test_expired_token_is_refused(app, entra):
    assert error_code(await run(app, entra.token(oid=ALICE, expires_in=-30))) == "unauthenticated"


async def test_another_users_session_is_not_found(app, entra):
    alice = await run(app, entra.token(oid=ALICE))
    session_id = alice[0]["session"]
    assert error_code(await run(app, entra.token(oid=BOB), session_id=session_id)) == "not_found"
    again = await run(app, entra.token(oid=ALICE), message="more", session_id=session_id)
    assert again[0]["session"] == session_id


async def test_client_state_cannot_set_tokens_or_server_keys(app, entra):
    state = {
        "draft": "kept",
        "temp:x": "dropped",
        "app:x": "dropped",
        "user:x": "dropped",
        "sdlc_active_team": "dropped",
        USER_TOKEN_STATE_KEY: "dropped",
    }
    events = await run(app, entra.token(oid=ALICE), state=state)
    session = await app.sessions.get_session(
        app_name="user_agent", user_id=ALICE, session_id=events[0]["session"]
    )
    assert session.state == {"draft": "kept", TITLE_STATE_KEY: "hello"}
    assert clean_state(state) == {"draft": "kept"}


async def test_threads_are_per_user_and_deletable_only_by_their_owner(app, entra):
    first = (await run(app, entra.token(oid=ALICE), message="Design   the ledger"))[0]["session"]
    await run(app, entra.token(oid=BOB), message="bob's")
    threads = await app.list_threads(entra.token(oid=ALICE))
    assert [(t["threadId"], t["title"]) for t in threads] == [(first, "Design the ledger")]
    assert error_code(await app.delete_thread(entra.token(oid=BOB), first)) == "not_found"
    assert await app.delete_thread(entra.token(oid=ALICE), first) == {"deleted": True}
    assert await app.list_threads(entra.token(oid=ALICE)) == []


async def test_empty_message_is_refused(app, entra):
    assert error_code(await run(app, entra.token(oid=ALICE), message="   ")) == "invalid_argument"


async def test_refusals_never_raise_or_carry_the_token(app, entra, caplog):
    """CH-0019: a raised error made Agent Runtime echo the arguments, the token included, into the
    error and its log. Every refusal is a result whose text and logs never contain the token."""
    expired = entra.token(oid=ALICE, expires_in=-30)
    results = [
        await run(app, expired),
        await app.list_threads(expired),
        await app.delete_thread(expired, "s1"),
        await app.list_threads("not.a.jwt"),
    ]
    assert [error_code(r) for r in results] == ["unauthenticated"] * 4
    for secret in (expired, "not.a.jwt"):
        assert secret not in repr(results)
        assert secret not in caplog.text


class Exploding(InMemorySessionService):
    def __init__(self, token):
        super().__init__()
        self.token = token

    async def list_sessions(self, **kw):
        raise RuntimeError(f"backend failed for {self.token}")


async def test_an_unexpected_error_is_internal_and_logs_only_its_type(entra, caplog):
    token = entra.token(oid=ALICE)
    app = UserAgentApp(
        verifier=entra.verifier(), agent=Echo(name="echo"), session_service=Exploding(token)
    )
    app.set_up()
    with caplog.at_level("WARNING"):
        result = await app.list_threads(token)
    assert error_code(result) == "internal"
    assert "RuntimeError" in caplog.text
    assert token not in repr(result) and token not in caplog.text


def test_operations_are_registered():
    ops = UserAgentApp().register_operations()
    assert ops == {"async": ["list_threads", "delete_thread"], "async_stream": ["stream_query"]}


def test_sessions_stay_in_the_engine_region_and_gemini_uses_the_model_region(monkeypatch, entra):
    """Agent Runtime sets GOOGLE_CLOUD_LOCATION to the engine's region; Gemini is not served there
    (CH-0014 fix: the first live run got 404 for the model)."""
    import user_agent.runtime_app as runtime_app

    seen = {}
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "asia-southeast1")
    monkeypatch.setenv("SDLC_MODEL_LOCATION", "global")
    monkeypatch.setattr(
        runtime_app,
        "_session_service_from_env",
        lambda location: seen.setdefault("sessions", location) and InMemorySessionService(),
    )
    app = UserAgentApp(verifier=entra.verifier(), agent=Echo(name="echo"))
    app.set_up()
    assert seen["sessions"] == "asia-southeast1"
    import os

    assert os.environ["GOOGLE_CLOUD_LOCATION"] == "global"

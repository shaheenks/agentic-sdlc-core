"""The user agent's Agent Runtime entry point (CH-0014): token check, oid binding, session
ownership, state cleaning, and the user token bound only for the call.

Offline: a stand-in agent reports what it sees (no model), sessions are in memory, tokens come
from the fake Entra issuer.
"""

import json
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
    """The code of a refusal (CH-0019: refusals are results, never exceptions). CH-0025: under
    `refusal`, never a top-level `error`, which google.genai takes for an API error."""
    if isinstance(result, list):
        assert len(result) == 1, result  # a refused stream is a single event, no session
        result = result[0]
    assert "error" not in result, result
    return result["refusal"]["code"]


async def test_a_refused_stream_event_is_not_read_as_an_api_error(app):
    """google.genai raises on any streamed chunk whose JSON starts with {"error": (CH-0025)."""
    import json

    (event,) = await run(app, "not.a.jwt")
    assert not json.dumps(event).startswith('{"error":')
    assert set(event) == {"refusal"} and set(event["refusal"]) == {"code", "message"}


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
    assert ops == {
        "async": ["list_threads", "get_thread", "delete_thread"],
        "async_stream": ["stream_query"],
    }


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


# --- GCP stack (CH-0022): the engine accepts Google ID tokens, the user id is `sub` ---------------

SUB_A, SUB_B = "1" * 21, "2" * 21


@pytest.fixture
def google_app():
    from tests.support.google import FakeGoogle

    google = FakeGoogle()
    sessions = InMemorySessionService()
    a = UserAgentApp(verifier=google.verifier(), agent=Echo(name="echo"), session_service=sessions)
    a.set_up()
    a.google = google
    return a


async def test_google_stack_streams_as_the_sub(google_app):
    events = await run(google_app, google_app.google.token(sub=SUB_A))
    assert texts(events) == [f"user={SUB_A} token=yes"]


async def test_google_stack_sessions_are_per_sub(google_app):
    google = google_app.google
    first = await run(google_app, google.token(sub=SUB_A))
    other = await run(google_app, google.token(sub=SUB_B), session_id=first[0]["session"])
    assert error_code(other) == "not_found"


async def test_each_stack_refuses_the_other_stacks_token(app, google_app, entra):
    assert error_code(await run(google_app, entra.token(oid=ALICE))) == "unauthenticated"
    assert error_code(await run(app, google_app.google.token(sub=SUB_A))) == "unauthenticated"


async def test_google_stack_refuses_another_domain(google_app):
    token = google_app.google.token(sub=SUB_A, email="x@elsewhere.test", hd="elsewhere.test")
    assert error_code(await run(google_app, token)) == "unauthenticated"


def test_the_stack_is_chosen_by_environment_and_fails_closed(monkeypatch):
    from sdlc_agent import runtime_guard
    from sdlc_auth.google import GOOGLE_ISSUER, GoogleTokenVerifier

    assert runtime_guard.GOOGLE_ISSUER == GOOGLE_ISSUER
    assert runtime_guard.identity_provider({}) == "entra"
    assert runtime_guard.identity_provider({"SDLC_IDENTITY_PROVIDER": " Google "}) == "google"
    with pytest.raises(SystemExit, match="fail closed"):
        runtime_guard.identity_provider({"SDLC_IDENTITY_PROVIDER": "github"})
    monkeypatch.setenv("SDLC_OAUTH_CLIENT_IDS", "client-a")
    monkeypatch.setenv("SDLC_ALLOWED_DOMAINS", "example.test")
    verifier = runtime_guard.verifier_from_env({"SDLC_IDENTITY_PROVIDER": "google"})
    assert isinstance(verifier, GoogleTokenVerifier)
    monkeypatch.delenv("SDLC_ALLOWED_DOMAINS")
    with pytest.raises(SystemExit, match="fail closed"):
        runtime_guard.verifier_from_env({"SDLC_IDENTITY_PROVIDER": "google"})


def test_principal_of_reads_each_stacks_claims():
    from sdlc_agent.runtime_guard import GOOGLE_ISSUER, principal_of

    google = principal_of(
        {"iss": GOOGLE_ISSUER, "sub": SUB_A, "email": "A@Example.Test", "hd": "example.test"}
    )
    assert (google.oid, google.upn, google.provider) == (SUB_A, "a@example.test", "google")
    entra = principal_of({"oid": ALICE, "tid": "t", "iss": "https://login.microsoftonline.com/t"})
    assert (entra.oid, entra.provider) == (ALICE, "entra")


# --- CH-0016: the UI names threads (AG-UI thread ids); get_thread replays one ----------------


async def test_a_ui_thread_id_names_one_session_per_user(app, entra):
    first = await run(app, entra.token(oid=ALICE), thread_id="t-1")
    again = await run(app, entra.token(oid=ALICE), message="more", thread_id="t-1")
    assert first[0]["session"] == again[0]["session"]
    bobs = await run(app, entra.token(oid=BOB), thread_id="t-1")  # the same name, his own session
    assert bobs[0]["session"] != first[0]["session"]
    threads = await app.list_threads(entra.token(oid=ALICE))
    assert [t["threadId"] for t in threads] == ["t-1"]


async def test_client_state_cannot_claim_a_thread(app, entra):
    await run(app, entra.token(oid=ALICE), thread_id="t-1")
    other = await run(app, entra.token(oid=ALICE), state={"sdlc_thread_id": "t-1"})
    threads = await app.list_threads(entra.token(oid=ALICE))
    assert sorted(t["threadId"] for t in threads) == sorted(["t-1", other[0]["session"]])


async def test_get_thread_replays_the_owners_conversation_as_ag_ui_messages(app, entra):
    from google.adk.events import Event as AdkEvent

    events = await run(app, entra.token(oid=ALICE), message="hello", thread_id="t-1")
    sid = events[0]["session"]
    session = await app.sessions.get_session(app_name=app._app_name, user_id=ALICE, session_id=sid)
    call = types.Part(function_call=types.FunctionCall(id="c1", name="whoami", args={"x": 1}))
    result = types.Part(
        function_response=types.FunctionResponse(id="c1", name="whoami", response={"ok": True})
    )
    for author, role, part in (("echo", "model", call), ("echo", "user", result)):
        await app.sessions.append_event(
            session,
            AdkEvent(
                author=author, invocation_id="i", content=types.Content(role=role, parts=[part])
            ),
        )
    got = await app.get_thread(entra.token(oid=ALICE), thread_id="t-1")
    assert got["threadId"] == "t-1"
    roles = [m["role"] for m in got["messages"]]
    assert roles == ["user", "assistant", "assistant", "tool"]
    assert got["messages"][0]["content"] == "hello"
    assert got["messages"][2]["toolCalls"] == [
        {"id": "c1", "type": "function", "function": {"name": "whoami", "arguments": '{"x": 1}'}}
    ]
    assert got["messages"][3]["toolCallId"] == "c1"
    assert json.loads(got["messages"][3]["content"]) == {"ok": True}
    assert all(m["id"] for m in got["messages"])


async def test_get_thread_and_delete_are_owner_only(app, entra):
    await run(app, entra.token(oid=ALICE), thread_id="t-1")
    assert error_code(await app.get_thread(entra.token(oid=BOB), thread_id="t-1")) == "not_found"
    assert error_code(await app.get_thread("not.a.jwt", thread_id="t-1")) == "unauthenticated"
    assert error_code(await app.delete_thread(entra.token(oid=BOB), "t-1")) == "not_found"
    assert await app.delete_thread(entra.token(oid=ALICE), "t-1") == {"deleted": True}
    assert await app.list_threads(entra.token(oid=ALICE)) == []


def test_get_thread_is_registered():
    assert "get_thread" in UserAgentApp().register_operations()["async"]


async def test_threads_from_before_thread_names_open_and_continue_by_session_id(app, entra):
    """Dev, 2026-11-16: conversations started before CH-0016 have no thread name, so list_threads
    names them by session id; opening or continuing one must reach that session, not a new one."""
    old = await run(app, entra.token(oid=ALICE), message="before names")  # no thread_id
    sid = old[0]["session"]
    assert [t["threadId"] for t in await app.list_threads(entra.token(oid=ALICE))] == [sid]
    got = await app.get_thread(entra.token(oid=ALICE), thread_id=sid)
    assert got["threadId"] == sid and got["messages"][0]["content"] == "before names"
    more = await run(app, entra.token(oid=ALICE), message="again", thread_id=sid)
    assert more[0]["session"] == sid
    assert len(await app.list_threads(entra.token(oid=ALICE))) == 1
    # still owner-only
    assert error_code(await app.get_thread(entra.token(oid=BOB), thread_id=sid)) == "not_found"
    bobs = await run(app, entra.token(oid=BOB), thread_id=sid)
    assert bobs[0]["session"] != sid

"""EntraUserBindingMiddleware: authentication, user binding and token context (no ADK needed)."""

import json

import httpx
import pytest
from sdlc_auth.adk import USER_TOKEN_STATE_KEY, get_user_token
from sdlc_web.middleware import EntraUserBindingMiddleware

OID_A = "aaaaaaaa-0000-0000-0000-00000000000a"


class Recorder:
    """Downstream ASGI app that records what it received and the token in context."""

    def __init__(self):
        self.calls: list[dict] = []

    async def __call__(self, scope, receive, send):
        body = b""
        if scope["type"] == "http":
            while True:
                message = await receive()
                body += message.get("body", b"")
                if not message.get("more_body"):
                    break
        self.calls.append(
            {
                "path": scope["path"],
                "body": body,
                "query": scope.get("query_string", b""),
                "token": get_user_token(None),
            }
        )
        if scope["type"] == "websocket":
            await send({"type": "websocket.accept"})
            return
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


@pytest.fixture
def downstream():
    return Recorder()


@pytest.fixture
def web(entra, downstream):
    app = EntraUserBindingMiddleware(downstream, entra.verifier())
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://agent")


def fwd(token: str) -> dict[str, str]:
    return {"X-Forwarded-Access-Token": token}


async def test_healthz_is_public(web, downstream):
    assert (await web.get("/healthz")).status_code == 200
    assert downstream.calls[0]["token"] is None


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Forwarded-Access-Token": "forged"}, {"Authorization": "Bearer not.a.jwt"}],
)
async def test_requests_without_valid_token_get_401(web, downstream, headers):
    resp = await web.get("/list-apps", headers=headers)
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"].startswith("Bearer")
    assert downstream.calls == []


@pytest.mark.parametrize(
    "token_kwargs", [{"expires_in": -30}, {"omit": ["scp"]}, {"audience": "someone-else"}]
)
async def test_expired_app_only_or_foreign_tokens_get_401(web, entra, downstream, token_kwargs):
    resp = await web.get("/list-apps", headers=fwd(entra.token(**token_kwargs)))
    assert resp.status_code == 401 and downstream.calls == []


async def test_bearer_header_also_accepted(web, entra, downstream):
    token = entra.token(oid=OID_A)
    assert (await web.get("/list-apps", headers={"Authorization": f"Bearer {token}"})).is_success
    assert downstream.calls[0]["token"] == token


async def test_session_paths_are_bound_to_token_oid(web, entra, downstream):
    token = entra.token(oid=OID_A)
    await web.get("/apps/bootstrap/users/someone-else/sessions", headers=fwd(token))
    await web.post("/apps/bootstrap/users/user/sessions/s1", headers=fwd(token), json={})
    await web.get("/apps/bootstrap/users/user", headers=fwd(token))
    assert [c["path"] for c in downstream.calls] == [
        f"/apps/bootstrap/users/{OID_A}/sessions",
        f"/apps/bootstrap/users/{OID_A}/sessions/s1",
        f"/apps/bootstrap/users/{OID_A}",
    ]
    assert all(c["token"] == token for c in downstream.calls)


RUN_BODIES = {
    "snake_case": {
        "app_name": "bootstrap",
        "user_id": "victim",
        "session_id": "s1",
        "state_delta": {USER_TOKEN_STATE_KEY: "stolen", "keep": 1},
    },
    # what the ADK dev UI sends
    "camelCase": {
        "appName": "bootstrap",
        "userId": "victim",
        "sessionId": "s1",
        "stateDelta": {USER_TOKEN_STATE_KEY: "stolen", "keep": 1},
    },
    # both spellings: ADK's alias (camelCase) wins, so both must be rewritten
    "mixed": {
        "appName": "bootstrap",
        "user_id": OID_A,
        "userId": "victim",
        "sessionId": "s1",
        "stateDelta": {USER_TOKEN_STATE_KEY: "stolen", "keep": 1},
    },
}


@pytest.mark.parametrize("path", ["/run", "/run_sse"])
@pytest.mark.parametrize("style", RUN_BODIES)
async def test_run_body_user_is_bound_and_smuggled_token_dropped(
    web, entra, downstream, path, style
):
    from google.adk.cli.api_server import RunAgentRequest

    token = entra.token(oid=OID_A)
    assert (await web.post(path, headers=fwd(token), json=RUN_BODIES[style])).is_success
    # Judge the rewritten body exactly as ADK will parse it.
    parsed = RunAgentRequest.model_validate(json.loads(downstream.calls[0]["body"]))
    assert parsed.user_id == OID_A
    assert parsed.session_id == "s1"
    assert parsed.state_delta == {"keep": 1}
    assert downstream.calls[0]["token"] == token


async def test_token_context_does_not_leak_between_requests(web, entra, downstream):
    a, b = entra.token(oid=OID_A), entra.token()
    await web.get("/list-apps", headers=fwd(a))
    await web.get("/list-apps", headers=fwd(b))
    assert [c["token"] for c in downstream.calls] == [a, b]
    assert get_user_token(None) is None


async def websocket(app, path="/run_live", headers=(), query=b""):
    sent = []

    async def receive():
        return {"type": "websocket.connect"}

    async def send(message):
        sent.append(message)

    await app(
        {"type": "websocket", "path": path, "headers": list(headers), "query_string": query},
        receive,
        send,
    )
    return sent


@pytest.mark.parametrize(
    "headers",
    [[], [(b"x-forwarded-access-token", b"forged")], [(b"authorization", b"Bearer not.a.jwt")]],
)
async def test_run_live_without_valid_token_is_closed(entra, downstream, headers):
    app = EntraUserBindingMiddleware(downstream, entra.verifier())
    assert await websocket(app, headers=headers) == [{"type": "websocket.close", "code": 1008}]
    assert downstream.calls == []


async def test_run_live_is_bound_to_the_token_user(entra, downstream):
    app = EntraUserBindingMiddleware(downstream, entra.verifier())
    token = entra.token(oid=OID_A)
    query = b"app_name=bootstrap&user_id=someone-else&user_id=x&session_id=s1&modalities=TEXT"
    sent = await websocket(
        app, headers=[(b"x-forwarded-access-token", token.encode())], query=query
    )
    assert sent == [{"type": "websocket.accept"}]
    [call] = downstream.calls
    params = call["query"].decode()
    assert f"user_id={OID_A}" in params and "someone-else" not in params
    assert params.count("user_id=") == 1 and "session_id=s1" in params
    assert call["token"] == token  # the agent's MCP calls carry the user's token
    assert get_user_token(None) is None  # and it does not leak past the connection


async def test_other_websockets_are_closed(entra, downstream):
    app = EntraUserBindingMiddleware(downstream, entra.verifier())
    token = entra.token(oid=OID_A)
    sent = await websocket(app, path="/ws", headers=[(b"x-forwarded-access-token", token.encode())])
    assert sent == [{"type": "websocket.close", "code": 1008}]
    assert downstream.calls == []

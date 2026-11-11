"""The real agent web app (ADK get_fast_api_app + middleware), without calling an LLM."""

from pathlib import Path

import httpx
import pytest
from sdlc_web.app import create_app

AGENTS_DIR = Path(__file__).resolve().parents[2] / "agents"
OID_A = "aaaaaaaa-0000-0000-0000-00000000000a"
OID_B = "bbbbbbbb-0000-0000-0000-00000000000b"


@pytest.fixture
def web(entra):
    app = create_app(AGENTS_DIR, entra.verifier(), host="127.0.0.1", port=8000)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://agent")


def as_user(entra, oid: str) -> dict[str, str]:
    return {"X-Forwarded-Access-Token": entra.token(oid=oid)}


async def test_health_public_everything_else_needs_sign_in(web):
    assert (await web.get("/healthz")).json() == {"status": "ok"}
    for path in ("/list-apps", "/dev-ui/", "/apps/user_agent/users/x/sessions"):
        assert (await web.get(path)).status_code == 401, path


async def test_signed_in_user_sees_agents(web, entra):
    resp = await web.get("/list-apps", headers=as_user(entra, OID_A))
    assert resp.status_code == 200 and "user_agent" in resp.json()


async def test_sessions_are_owned_by_the_token_user(web, entra):
    # The UI sends whatever user id it likes ("user"); the session belongs to the token's oid.
    created = await web.post(
        "/apps/user_agent/users/user/sessions", headers=as_user(entra, OID_A), json={}
    )
    assert created.status_code == 200, created.text
    session = created.json()
    assert session["userId"] == OID_A

    mine = await web.get("/apps/user_agent/users/user/sessions", headers=as_user(entra, OID_A))
    assert session["id"] in {s["id"] for s in mine.json()}

    # User B asks for A's sessions by A's oid and by the shared UI id: sees none of them.
    for uid in (OID_A, "user"):
        theirs = await web.get(
            f"/apps/user_agent/users/{uid}/sessions", headers=as_user(entra, OID_B)
        )
        assert session["id"] not in {s["id"] for s in theirs.json()}
    direct = await web.get(
        f"/apps/user_agent/users/{OID_A}/sessions/{session['id']}", headers=as_user(entra, OID_B)
    )
    assert direct.status_code == 404


# --- ADK developer tools (/dev/*) ------------------------------------------------------------


async def _new_session(web, entra, oid: str) -> str:
    resp = await web.post(
        "/apps/user_agent/users/user/sessions", headers=as_user(entra, oid), json={}
    )
    return resp.json()["id"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/dev/apps/user_agent/builder/save"),
        ("POST", "/dev/apps/user_agent/deploy/cloud_run"),
        ("POST", "/dev/apps/user_agent/deploy/agent_engine"),
        ("POST", "/dev/apps/user_agent/eval_sets/es1/add_session"),
        ("POST", "/dev/apps/user_agent/tests/run"),
        ("GET", "/dev/apps/user_agent/debug/trace/some-event-id"),
        ("GET", "/dev/apps/user_agent/deploy/defaults"),
    ],
)
async def test_developer_tools_are_refused(web, entra, method, path):
    resp = await web.request(method, path, headers=as_user(entra, OID_A), json={})
    assert resp.status_code == 403, (path, resp.status_code)


async def test_ui_load_listings_are_empty_and_graphs_work(web, entra):
    for path in ("eval_sets", "eval-results", "tests", "builder"):
        resp = await web.get(f"/dev/apps/user_agent/{path}", headers=as_user(entra, OID_A))
        assert (resp.status_code, resp.json()) == (200, []), path
    graph = await web.get("/dev/apps/user_agent/build_graph", headers=as_user(entra, OID_A))
    assert graph.status_code == 200


async def test_session_trace_only_for_the_owner(web, entra):
    sid = await _new_session(web, entra, OID_A)
    trace = f"/dev/apps/user_agent/debug/trace/session/{sid}"
    assert (await web.get(trace, headers=as_user(entra, OID_A))).status_code == 200
    assert (await web.get(trace, headers=as_user(entra, OID_B))).status_code == 404


async def test_dev_user_routes_are_bound_to_token_user(web, entra):
    sid = await _new_session(web, entra, OID_A)
    # B addresses A's session under A's oid on the dev graph route: rebound to B -> not found.
    path = f"/dev/apps/user_agent/users/{OID_A}/sessions/{sid}/events/e1/graph"
    resp = await web.get(path, headers=as_user(entra, OID_B))
    assert resp.status_code != 200 or sid not in resp.text


async def test_dev_tools_switch_restores_developer_routes(entra):
    app = create_app(AGENTS_DIR, entra.verifier(), host="127.0.0.1", port=8000, dev_tools=True)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://agent"
    ) as web:
        resp = await web.get("/dev/apps/user_agent/deploy/defaults", headers=as_user(entra, OID_A))
    assert resp.status_code != 403


async def test_bare_chat_path_redirects_to_the_chat_app(web, entra):
    # oauth2-proxy routes the "/chat/" prefix to the CopilotKit app; "/chat" reaches the agent
    resp = await web.get("/chat", headers=as_user(entra, OID_A))
    assert resp.status_code == 307 and resp.headers["location"] == "/chat/"
    assert (await web.get("/chat")).status_code == 401  # still behind sign-in


async def test_public_origin_is_allowed_when_the_proxy_rewrites_host(entra):
    # Cloud Run: oauth2-proxy sends Host 127.0.0.1:8000, the browser sends its real Origin
    public = "https://sdlc-app-dev-123.asia-southeast1.run.app"
    headers = {**as_user(entra, OID_A), "Origin": public, "Host": "127.0.0.1:8000"}
    plain = create_app(AGENTS_DIR, entra.verifier(), host="127.0.0.1", port=8000)
    allowed = create_app(
        AGENTS_DIR, entra.verifier(), host="127.0.0.1", port=8000, allow_origins=[public]
    )
    for app, status in ((plain, 403), (allowed, 200)):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000"
        ) as client:
            assert (await client.get("/list-apps", headers=headers)).status_code == status


async def test_me_returns_only_name_and_sign_in_name(web, entra):
    token = entra.token(oid=OID_A, upn="ana@example.com", name="Ana Dev", roles=["g1"])
    resp = await web.get("/me", headers={"X-Forwarded-Access-Token": token})
    assert resp.status_code == 200 and resp.headers["cache-control"] == "no-store"
    assert resp.json() == {"name": "Ana Dev", "upn": "ana@example.com"}  # no oid, groups or token
    assert (await web.get("/me")).status_code == 401


async def test_root_redirects_to_the_chat_app_when_it_is_on(entra):
    from sdlc_web.middleware import EntraUserBindingMiddleware

    async def adk(scope, receive, send):  # stands in for ADK, whose "/" goes to /dev-ui/
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"adk"})

    for home, status in (("/chat/", 307), (None, 200)):
        app = EntraUserBindingMiddleware(adk, entra.verifier(), home_path=home)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://agent"
        ) as client:
            resp = await client.get("/", headers=as_user(entra, OID_A))
            assert resp.status_code == status
            if home:
                assert resp.headers["location"] == "/chat/"
                assert (await client.get("/")).status_code == 401  # still behind sign-in
            assert (await client.get("/dev-ui/", headers=as_user(entra, OID_A))).status_code == 200

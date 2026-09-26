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
    for path in ("/list-apps", "/dev-ui/", "/apps/bootstrap/users/x/sessions"):
        assert (await web.get(path)).status_code == 401, path


async def test_signed_in_user_sees_agents(web, entra):
    resp = await web.get("/list-apps", headers=as_user(entra, OID_A))
    assert resp.status_code == 200 and "bootstrap" in resp.json()


async def test_sessions_are_owned_by_the_token_user(web, entra):
    # The UI sends whatever user id it likes ("user"); the session belongs to the token's oid.
    created = await web.post(
        "/apps/bootstrap/users/user/sessions", headers=as_user(entra, OID_A), json={}
    )
    assert created.status_code == 200, created.text
    session = created.json()
    assert session["userId"] == OID_A

    mine = await web.get("/apps/bootstrap/users/user/sessions", headers=as_user(entra, OID_A))
    assert session["id"] in {s["id"] for s in mine.json()}

    # User B asks for A's sessions by A's oid and by the shared UI id: sees none of them.
    for uid in (OID_A, "user"):
        theirs = await web.get(
            f"/apps/bootstrap/users/{uid}/sessions", headers=as_user(entra, OID_B)
        )
        assert session["id"] not in {s["id"] for s in theirs.json()}
    direct = await web.get(
        f"/apps/bootstrap/users/{OID_A}/sessions/{session['id']}", headers=as_user(entra, OID_B)
    )
    assert direct.status_code == 404

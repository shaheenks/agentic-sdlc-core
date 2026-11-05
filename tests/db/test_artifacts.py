"""version-03 P5 (F1) on a real Postgres: artifact metadata is owner-only under RLS, and the MCP
artifact tools save, list, read and delete only the caller's own documents.

Needs the Postgres container and .env passwords:  uv run --env-file .env pytest tests/db
"""

import asyncio
import json
import uuid

import httpx
import psycopg
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import RemoteAuthProvider
from psycopg_pool import AsyncConnectionPool
from sdlc_artifacts import MemoryArtifactStore
from sdlc_auth.entra import entra_issuer
from sdlc_core_mcp import artifact_tools
from sdlc_core_mcp.artifact_tools import Artifacts
from sdlc_core_mcp.knowledge_tools import Knowledge
from sdlc_core_mcp.server import build_http_app, build_server
from sdlc_db import HashEmbedder

from tests.support import db
from tests.support.entra import G_ENG_ALL, TENANT
from tests.support.servers import free_port, serve

pytestmark = pytest.mark.skipif(bool(db.available()), reason=str(db.available()))

ALICE = "aaaaaaaa-0000-0000-0000-00000000000a"
BOB = "bbbbbbbb-0000-0000-0000-00000000000b"
SECRET_TEXT = "Ledger redesign: confidential draft"


@pytest.fixture(scope="module")
def database():
    db.create_test_database()


def as_app(oid: str | None, sql_text: str, params=()):
    """One transaction as sdlc_app with app.user_oid set (or not)."""
    with psycopg.connect(db.db_conninfo("app")) as conn, conn.transaction():
        if oid:
            conn.execute("SELECT set_config('app.user_oid', %s, true)", (oid,))
        cur = conn.execute(sql_text, params)
        return cur.fetchall() if cur.description else cur.rowcount


def insert_sql(owner: str) -> tuple[str, tuple]:
    return (
        "INSERT INTO artifacts (id, owner_oid, name, media_type, size_bytes, sha256, expires_at)"
        " VALUES (%s, %s, 'a.md', 'text/markdown', 1, %s, now() + interval '1 day')",
        (str(uuid.uuid4()), owner, "0" * 64),
    )


# --- database-level guarantees ------------------------------------------------------------------


def test_no_owner_context_sees_and_writes_nothing(database):
    as_app(ALICE, *insert_sql(ALICE))
    assert as_app(None, "SELECT count(*) FROM artifacts") == [(0,)]
    with pytest.raises(psycopg.errors.InsufficientPrivilege):  # RLS WITH CHECK
        as_app(None, *insert_sql(ALICE))


def test_owner_sees_only_own_rows_and_cannot_write_for_others(database):
    as_app(BOB, *insert_sql(BOB))
    alice_rows = as_app(ALICE, "SELECT owner_oid FROM artifacts")
    assert alice_rows and {r[0] for r in alice_rows} == {ALICE}
    assert as_app(ALICE, "DELETE FROM artifacts WHERE owner_oid = %s", (BOB,)) == 0
    assert as_app(BOB, "SELECT count(*) FROM artifacts") == [(1,)]
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_app(ALICE, *insert_sql(BOB))


def test_app_role_has_no_update_and_knowledge_stays_read_only(database):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_app(ALICE, "UPDATE artifacts SET name = 'b.md'")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_app(ALICE, "DELETE FROM chunks")


# --- through the MCP server ---------------------------------------------------------------------


@pytest.fixture
def mcp(database, entra, store):
    """MCP server on the test database (sdlc_app pool) with an in-memory content store."""
    port = free_port()
    auth = RemoteAuthProvider(
        token_verifier=entra.verifier(),
        authorization_servers=[entra_issuer(TENANT)],
        base_url=f"http://127.0.0.1:{port}",
    )
    pool = AsyncConnectionPool(db.db_conninfo("app"), min_size=1, max_size=4, open=False)
    content = MemoryArtifactStore()
    artifacts = Artifacts(content, Knowledge(pool, HashEmbedder()), retention_days=7)
    server = build_server(store, auth, artifacts=artifacts)
    with serve(build_http_app(server, store), port) as url:
        yield url, content, artifacts


async def call(url, entra, oid, tool, args=None, groups=(G_ENG_ALL,)):
    async with Client(f"{url}/mcp", auth=entra.token(oid=oid, groups=list(groups))) as c:
        return (await c.call_tool(tool, args or {})).data


def audit(caplog, event):
    records = [json.loads(r.getMessage()) for r in caplog.records if r.name == "sdlc.audit"]
    return [r for r in records if r["event"] == event]


async def test_owner_round_trip_and_other_user_gets_not_found(mcp, entra, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    url, content, _ = mcp
    saved = await call(
        url, entra, ALICE, "save_artifact", {"name": "ledger design.md", "content": SECRET_TEXT}
    )
    aid = saved["id"]
    assert saved["download_path"] == f"/artifacts/{aid}" and saved["size_bytes"] == len(SECRET_TEXT)
    assert content.objects[f"artifacts/{ALICE}/{aid}"] == SECRET_TEXT.encode()

    listed = await call(url, entra, ALICE, "list_artifacts")
    assert aid in {a["id"] for a in listed["artifacts"]}
    assert (await call(url, entra, ALICE, "read_artifact", {"artifact_id": aid}))[
        "content"
    ] == SECRET_TEXT

    # Bob: not in his list; read and delete answer "not found" (no hint that it exists)
    assert aid not in {
        a["id"] for a in (await call(url, entra, BOB, "list_artifacts"))["artifacts"]
    }
    for tool in ("read_artifact", "delete_artifact"):
        with pytest.raises(ToolError, match="artifact not found"):
            await call(url, entra, BOB, tool, {"artifact_id": aid})
    with pytest.raises(ToolError, match="artifact not found"):
        await call(url, entra, ALICE, "read_artifact", {"artifact_id": "not-a-uuid"})

    assert (await call(url, entra, ALICE, "delete_artifact", {"artifact_id": aid}))["deleted"]
    assert f"artifacts/{ALICE}/{aid}" not in content.objects
    with pytest.raises(ToolError, match="artifact not found"):
        await call(url, entra, ALICE, "read_artifact", {"artifact_id": aid})

    created = [r for r in audit(caplog, "artifact_change") if r["artifact_id"] == aid]
    assert [(r["oid"], r["action"], r["outcome"]) for r in created] == [
        (ALICE, "create", "ok"),
        (BOB, "delete", "not_found"),  # attempts on another user's artifact are audited too
        (ALICE, "delete", "ok"),
    ]
    assert audit(caplog, "artifact_access")  # reads are audited too
    flat = json.dumps([r for r in caplog.records if r.name == "sdlc.audit"], default=str)
    assert SECRET_TEXT not in flat and "ledger design.md" not in caplog.text


async def test_bad_input_and_no_role_are_refused(mcp, entra):
    url, _, _ = mcp
    with pytest.raises(ToolError, match="must end with .md"):
        await call(url, entra, ALICE, "save_artifact", {"name": "x.html", "content": "<b>"})
    with pytest.raises(ToolError):  # no sdlc groups: signed-in only, the tool is not granted
        await call(url, entra, ALICE, "list_artifacts", groups=())


async def test_live_limit(mcp, entra, monkeypatch):
    url, _, _ = mcp
    carol = str(uuid.uuid4())
    monkeypatch.setattr(artifact_tools, "MAX_LIVE_PER_USER", 2)
    for i in range(2):
        await call(url, entra, carol, "save_artifact", {"name": f"r{i}.md", "content": "x"})
    with pytest.raises(ToolError, match="the limit"):
        await call(url, entra, carol, "save_artifact", {"name": "r2.md", "content": "x"})


async def test_expired_artifacts_disappear_and_their_content_is_removed(mcp, entra):
    url, content, artifacts = mcp
    dave = str(uuid.uuid4())
    artifacts.retention_days = 1 / 86400  # one second
    saved = await call(url, entra, dave, "save_artifact", {"name": "old.md", "content": "x"})
    await asyncio.sleep(1.5)
    assert (await call(url, entra, dave, "list_artifacts"))["artifacts"] == []
    assert f"artifacts/{dave}/{saved['id']}" not in content.objects


# --- download API (F2): what the browser reaches through oauth2-proxy at /artifacts/ -------------


async def test_download_api_owner_only(mcp, entra, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    url, _, _ = mcp
    saved = await call(url, entra, ALICE, "save_artifact", {"name": "stories.md", "content": "# S"})
    aid = saved["id"]

    def as_user(oid, groups=(G_ENG_ALL,)):
        # oauth2-proxy forwards the session's access token in this header
        token = entra.token(oid=oid, groups=list(groups))
        return httpx.AsyncClient(base_url=url, headers={"X-Forwarded-Access-Token": token})

    async with as_user(ALICE) as alice, as_user(BOB) as bob, as_user(ALICE, ()) as nobody:
        listed = (await alice.get("/artifacts/")).json()["artifacts"]
        assert aid in {a["id"] for a in listed}

        r = await alice.get(f"/artifacts/{aid}")
        assert r.status_code == 200 and r.content == b"# S"
        assert r.headers["content-disposition"] == 'attachment; filename="stories.md"'
        assert r.headers["content-type"].startswith("text/markdown")
        assert r.headers["x-content-type-options"] == "nosniff"
        assert "sandbox" in r.headers["content-security-policy"]

        assert (await bob.get(f"/artifacts/{aid}")).status_code == 404  # same as missing
        assert (await bob.get("/artifacts/not-a-uuid")).status_code == 404
        assert aid not in {a["id"] for a in (await bob.get("/artifacts/")).json()["artifacts"]}
        assert (
            await bob.delete(f"/artifacts/{aid}", headers={"X-SDLC-Request": "1"})
        ).status_code == 404
        assert (await nobody.get("/artifacts/")).status_code == 403  # no artifact tool, no API
        async with httpx.AsyncClient(base_url=url) as anonymous:
            assert (await anonymous.get(f"/artifacts/{aid}")).status_code == 401

        assert (await alice.delete(f"/artifacts/{aid}")).status_code == 403  # no write header
        r = await alice.delete(f"/artifacts/{aid}", headers={"X-SDLC-Request": "1"})
        assert r.status_code == 200 and r.json()["deleted"] is True
        assert (await alice.get(f"/artifacts/{aid}")).status_code == 404

    downloads = [r for r in audit(caplog, "artifact_access") if r["action"] == "download"]
    assert {(r["oid"], r["outcome"]) for r in downloads} >= {(ALICE, "ok"), (BOB, "not_found")}
    assert all("stories.md" not in json.dumps(r) for r in downloads)

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
    row_id = str(uuid.uuid4())
    return (
        "INSERT INTO artifacts (id, document_id, owner_oid, name, media_type, size_bytes, sha256,"
        " expires_at) VALUES (%s, %s, %s, 'a.md', 'text/markdown', 1, %s,"
        " now() + interval '1 day')",
        (row_id, row_id, owner, "0" * 64),
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


async def call(url, entra, oid, tool, args=None, roles=(G_ENG_ALL,)):
    async with Client(f"{url}/mcp", auth=entra.token(oid=oid, roles=list(roles))) as c:
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
    with pytest.raises(ToolError):  # no app roles: signed-in only, the tool is not granted
        await call(url, entra, ALICE, "list_artifacts", roles=())


async def test_document_limit_counts_documents_not_versions(mcp, entra, monkeypatch, caplog):
    """CH-0004: a document counts once against the per-user limit, however many versions."""
    caplog.set_level("INFO", logger="sdlc.audit")
    url, _, _ = mcp
    carol = str(uuid.uuid4())
    monkeypatch.setattr(artifact_tools, "MAX_LIVE_PER_USER", 2)
    monkeypatch.setattr(artifact_tools, "MAX_VERSIONS_PER_DOCUMENT", 3)

    def save(**kw):
        return call(url, entra, carol, "save_artifact", {"content": "x", **kw})

    for name in ("a.md", "b.md"):  # two documents with three versions each: six rows, allowed
        doc = (await save(name=name))["id"]
        for base in (1, 2):
            await save(name=name, replaces=doc, base_version=base)
    listed = await call(url, entra, carol, "list_artifacts")
    assert len(listed["artifacts"]) == 2
    assert (listed["limit"], listed["versions_per_document"]) == (2, 3)

    with pytest.raises(ToolError, match="you have 2 saved documents"):
        await save(name="c.md")
    limits = [r for r in audit(caplog, "artifact_change") if r["outcome"] == "limit"]
    assert [(r["action"], r["limit"]) for r in limits] == [("create", "documents")]


async def test_version_limit_per_document(mcp, entra, monkeypatch, caplog):
    """CH-0004: a document keeps at most MAX_VERSIONS_PER_DOCUMENT versions; the refusal says
    to save a new document or delete this one."""
    caplog.set_level("INFO", logger="sdlc.audit")
    url, _, _ = mcp
    gus = str(uuid.uuid4())
    monkeypatch.setattr(artifact_tools, "MAX_VERSIONS_PER_DOCUMENT", 2)

    def save(**kw):
        return call(url, entra, gus, "save_artifact", {"name": "d.md", "content": "x", **kw})

    doc = (await save())["id"]
    await save(replaces=doc, base_version=1)
    with pytest.raises(ToolError, match="already has 2 versions.*new document.*delete_artifact"):
        await save(replaces=doc, base_version=2)
    limits = [r for r in audit(caplog, "artifact_change") if r["outcome"] == "limit"]
    assert [(r["action"], r["artifact_id"], r["limit"]) for r in limits] == [
        ("update", doc, "versions")
    ]
    listed = (await call(url, entra, gus, "list_artifacts"))["artifacts"]
    assert [(a["id"], a["version"]) for a in listed] == [(doc, 2)]  # nothing saved
    assert (await save(name="e.md"))["version"] == 1  # a new document is still fine


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

    def as_user(oid, roles=(G_ENG_ALL,)):
        # oauth2-proxy forwards the session's access token in this header
        token = entra.token(oid=oid, roles=list(roles))
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


# --- versions (F6): revisions of one document keep its id and link ------------------------------


async def test_versions_of_one_document(mcp, entra, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    url, content, _ = mcp
    erin = str(uuid.uuid4())
    v1 = await call(url, entra, erin, "save_artifact", {"name": "design.md", "content": "one"})
    doc = v1["id"]
    assert (v1["version"], v1["versions"]) == (1, 1)
    v2 = await call(
        url,
        entra,
        erin,
        "save_artifact",
        {"name": "design.md", "content": "two", "replaces": doc, "base_version": 1},
    )
    assert (v2["id"], v2["version"], v2["download_path"]) == (doc, 2, f"/artifacts/{doc}")

    listed = (await call(url, entra, erin, "list_artifacts"))["artifacts"]
    assert [(a["id"], a["version"], a["versions"]) for a in listed] == [(doc, 2, 2)]
    read = lambda **kw: call(url, entra, erin, "read_artifact", {"artifact_id": doc, **kw})  # noqa: E731
    assert (await read())["content"] == "two"
    assert (await read(version=1))["content"] == "one"
    with pytest.raises(ToolError, match="artifact not found"):
        await read(version=3)

    # another user cannot add a version to it (same answer as a missing document)
    with pytest.raises(ToolError, match="artifact not found"):
        await call(
            url,
            entra,
            BOB,
            "save_artifact",
            {"name": "x.md", "content": "x", "replaces": doc, "base_version": 2},
        )

    token = entra.token(oid=erin, roles=[G_ENG_ALL])
    async with httpx.AsyncClient(base_url=url, headers={"X-Forwarded-Access-Token": token}) as h:
        latest = await h.get(f"/artifacts/{doc}")
        assert latest.content == b"two" and latest.headers["x-sdlc-artifact-version"] == "2"
        assert (await h.get(f"/artifacts/{doc}?version=1")).content == b"one"
        for bad in ("x", "0", "²", "", "1e3", "9999999999"):  # "²" passed isdigit() (was a 500)
            r = await h.get(f"/artifacts/{doc}", params={"version": bad})
            assert r.status_code == 404, bad
        versions = (await h.get(f"/artifacts/{doc}/versions")).json()["versions"]
        assert [v["version"] for v in versions] == [2, 1]
        r = await h.delete(f"/artifacts/{doc}", headers={"X-SDLC-Request": "1"})
        assert r.json() == {"id": doc, "deleted": True, "versions": 2}
        assert (await h.get(f"/artifacts/{doc}/versions")).status_code == 404
    assert not [k for k in content.objects if k.startswith(f"artifacts/{erin}/")]

    changes = [r for r in audit(caplog, "artifact_change") if r["artifact_id"] == doc]
    assert [(r["action"], r["outcome"]) for r in changes] == [
        ("create", "ok"),
        ("update", "ok"),
        ("update", "not_found"),  # Bob's attempt
        ("delete", "ok"),
    ]


async def test_revisions_never_drop_newer_versions(mcp, entra, caplog):
    """Review comments on an older version must not overwrite newer edits (base_version)."""
    caplog.set_level("INFO", logger="sdlc.audit")
    url, _, _ = mcp
    fay = str(uuid.uuid4())
    save = lambda **kw: call(url, entra, fay, "save_artifact", {"name": "d.md", **kw})  # noqa: E731
    doc = (await save(content="one"))["id"]
    await save(content="two", replaces=doc, base_version=1)

    with pytest.raises(ToolError, match="pass base_version"):
        await save(content="x", replaces=doc)
    with pytest.raises(ToolError, match="latest version is 2"):
        await save(content="from v1", replaces=doc, base_version=1)
    stale = [r for r in audit(caplog, "artifact_change") if r["outcome"] == "stale"]
    assert [(r["base_version"], r["latest_version"]) for r in stale] == [(1, 2)]
    listed = (await call(url, entra, fay, "list_artifacts"))["artifacts"]
    assert [(a["id"], a["version"]) for a in listed] == [(doc, 2)]  # nothing saved

    v3 = await save(content="three", replaces=doc, base_version=2)
    assert v3["version"] == 3


async def test_numbered_read_matches_the_viewer(mcp, entra):
    """read_artifact(numbered=true) numbers lines as the chat's viewer does; saving that output
    back unchanged is refused."""
    url, _, _ = mcp
    gus = str(uuid.uuid4())
    text = "# Title\r\n\nbody\twith tab\n"
    doc = (await call(url, entra, gus, "save_artifact", {"name": "n.md", "content": text}))["id"]
    read = await call(url, entra, gus, "read_artifact", {"artifact_id": doc, "numbered": True})
    assert read["numbered"] is True
    assert read["content"] == "1\t# Title\n2\t\n3\tbody\twith tab\n4\t"
    plain = await call(url, entra, gus, "read_artifact", {"artifact_id": doc})
    assert plain["content"] == text and "numbered" not in plain

    with pytest.raises(ToolError, match="line numbers"):
        await call(
            url,
            entra,
            gus,
            "save_artifact",
            {"name": "n.md", "content": read["content"], "replaces": doc, "base_version": 1},
        )


def test_looks_numbered():
    assert artifact_tools.looks_numbered("1\ta\n2\tb")
    assert not artifact_tools.looks_numbered("1\ta")  # one line: too little to tell
    assert not artifact_tools.looks_numbered("1\ta\n3\tb")  # not 1, 2, 3, ...
    assert not artifact_tools.looks_numbered("id\tname\n1\tx")  # TSV with a header

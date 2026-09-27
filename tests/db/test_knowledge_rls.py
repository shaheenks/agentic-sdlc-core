"""Stage 5: RLS on a real Postgres, ingest, and search_knowledge per persona.

Runs against a throwaway `sdlc_test` database (tests/support/db.py) with the real roles.
Needs the Postgres container and .env passwords:  uv run --env-file .env pytest tests/db
"""

import psycopg
import pytest
from fastmcp import Client
from fastmcp.server.auth import RemoteAuthProvider
from psycopg_pool import AsyncConnectionPool
from sdlc_auth.entra import entra_issuer
from sdlc_config import load_snapshot, resolve
from sdlc_db import HashEmbedder, rls_settings, search
from sdlc_mcp_bootstrap.knowledge_tools import Knowledge
from sdlc_mcp_bootstrap.server import build_http_app, build_server

from tests.support import db
from tests.support.config import make_config_dir
from tests.support.db import app_query, ingest_as_ingest_role, run
from tests.support.entra import (
    G_ENG_ALL,
    G_PAYMENTS_DEVS,
    G_PLATFORM_DEVS,
    TENANT,
    TEST_ENV,
)
from tests.support.graph import VocabularyExtractor
from tests.support.servers import free_port, serve

pytestmark = pytest.mark.skipif(bool(db.available()), reason=str(db.available()))

G_PAYMENTS_LEADS = "00000000-0000-0000-0000-000000000003"
EMBEDDER = HashEmbedder()


async def _ingest(snapshot, repo_root, sources=None):
    return await ingest_as_ingest_role(
        snapshot, repo_root, EMBEDDER, VocabularyExtractor(), sources
    )


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    """Fresh sdlc_test database with the sample corpus ingested (hash embeddings)."""
    db.create_test_database()
    config_dir = make_config_dir(tmp_path_factory.mktemp("repo"))
    snapshot = load_snapshot(config_dir, "local", TEST_ENV)
    reports = run(_ingest(snapshot, config_dir.parent))
    return config_dir, snapshot, {r.source_id: r for r in reports}


def sources_seen(policy) -> dict[str, int]:
    rows = app_query("SELECT source_id, count(*) FROM chunks GROUP BY 1", policy)
    return dict(rows)


# --- database-level guarantees ------------------------------------------------------------------


def test_ingest_wrote_every_source(corpus):
    _, _, reports = corpus
    assert {sid: r.chunks_written > 0 for sid, r in reports.items()} == {
        "eng-standards": True,
        "payments-code": True,
        "payments-incidents": True,
        "platform-infra": True,
    }


def test_no_rls_context_means_no_rows(corpus):
    for table in ("sources", "documents", "chunks"):
        assert app_query(f"SELECT count(*) FROM {table}") == [(0,)], table  # noqa: S608


def test_owner_is_subject_to_forced_rls(corpus):
    with psycopg.connect(db.db_conninfo("owner")) as conn:
        assert conn.execute("SELECT count(*) FROM chunks").fetchone() == (0,)


def test_app_role_cannot_write(corpus):
    with psycopg.connect(db.db_conninfo("app")) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM chunks")


def test_forged_context_values_are_rejected(corpus):
    snap = corpus[1]
    policy = resolve(snap, ["eng-all"])
    object.__setattr__(policy, "data_sources", {"x},{payments-code": ()})
    object.__setattr__(policy, "source_classification", {"x},{payments-code": 0})
    with pytest.raises(ValueError, match="invalid source id"):
        rls_settings(policy)


# --- per persona -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("groups", "expected"),
    [
        ([], set()),
        (["eng-all"], {"eng-standards"}),
        (["eng-all", "payments-devs"], {"eng-standards", "payments-code"}),  # not confidential
        (["eng-all", "payments-leads"], {"eng-standards", "payments-code", "payments-incidents"}),
        (["eng-all", "platform-devs"], {"eng-standards", "platform-infra"}),
        (
            ["platform-admins"],
            {"eng-standards", "payments-code", "payments-incidents", "platform-infra"},
        ),
    ],
)
def test_rows_visible_per_persona(corpus, groups, expected):
    assert set(sources_seen(resolve(corpus[1], groups))) == expected


def test_search_returns_only_permitted_sources(corpus):
    snap = corpus[1]

    async def go(groups):
        async with await psycopg.AsyncConnection.connect(db.db_conninfo("app")) as conn:
            [vec] = EMBEDDER.embed(["How are refunds retried after a timeout?"], "query")
            return await search(conn, resolve(snap, groups), vec, k=20)

    dev = run(go(["eng-all", "payments-devs"]))
    platform = run(go(["eng-all", "platform-devs"]))
    assert dev and {h.source_id for h in dev} <= {"eng-standards", "payments-code"}
    assert {h.source_id for h in platform} <= {"eng-standards", "platform-infra"}
    # hash embeddings only share words, so check membership, not exact ranking
    assert dev[0].source_id == "payments-code"
    assert any(h.path == "docs/refunds.md" and "retried" in h.content for h in dev)


# --- incremental ingest --------------------------------------------------------------------------


def test_reingest_skips_changes_and_deletes(corpus):
    config_dir, _, _ = corpus
    snapshot = load_snapshot(config_dir, "local", TEST_ENV)
    unchanged = run(_ingest(snapshot, config_dir.parent, ["eng-standards"]))[0]
    assert (unchanged.files_changed, unchanged.files_unchanged) == (0, 5)

    folder = config_dir.parent / "samples/sources/eng-standards"
    (folder / "api-design.md").write_text("# API design\n\nUse plural nouns.\n")
    (folder / "security-baseline.md").unlink()
    report = run(_ingest(snapshot, config_dir.parent, ["eng-standards"]))[0]
    assert (report.files_changed, report.files_unchanged, report.files_deleted) == (1, 3, 1)
    admin = resolve(snapshot, ["platform-admins"])
    paths = {
        p
        for (p,) in app_query("SELECT path FROM documents WHERE source_id = 'eng-standards'", admin)
    }
    assert paths == {
        "api-design.md",
        "code-review-guidelines.md",
        "incident-management.md",
        "service-tiers.md",
    }


def test_classification_change_applies_to_existing_rows(corpus):
    config_dir, _, _ = corpus
    source = config_dir / "sources/payments-code.yaml"
    source.write_text(
        source.read_text().replace("classification: internal", "classification: confidential")
    )
    snapshot = load_snapshot(config_dir, "local", TEST_ENV)
    run(_ingest(snapshot, config_dir.parent, ["payments-code"]))
    dev = resolve(snapshot, ["eng-all", "payments-devs"])  # ceiling internal
    lead = resolve(snapshot, ["eng-all", "payments-leads"])  # ceiling confidential
    assert "payments-code" not in sources_seen(dev)
    assert "payments-code" in sources_seen(lead)
    source.write_text(
        source.read_text().replace("classification: confidential", "classification: internal")
    )
    run(_ingest(load_snapshot(config_dir, "local", TEST_ENV), config_dir.parent, ["payments-code"]))


def test_raised_classification_applies_without_reingest(corpus):
    """Config says confidential, rows still say internal: the payments dev loses access on the
    next request (readable_sources), before any ingest re-stamps the rows."""
    config_dir, _, _ = corpus
    source = config_dir / "sources/payments-code.yaml"
    original = source.read_text()
    source.write_text(original.replace("classification: internal", "classification: confidential"))
    try:
        snapshot = load_snapshot(config_dir, "local", TEST_ENV)  # no ingest after this change
        dev = resolve(snapshot, ["eng-all", "payments-devs"])
        lead = resolve(snapshot, ["eng-all", "payments-leads"])
        assert "payments-code" in dev.data_sources and "payments-code" not in dev.readable_sources
        assert "payments-code" not in sources_seen(dev)
        assert "payments-code" in sources_seen(lead)
    finally:
        source.write_text(original)


def test_lowered_classification_waits_for_reingest(corpus):
    """Config lowered below the rows' stamp: rows stay hidden until ingest re-stamps them
    (fail closed)."""
    config_dir, _, _ = corpus
    source = config_dir / "sources/payments-incidents.yaml"
    original = source.read_text()
    source.write_text(original.replace("classification: confidential", "classification: internal"))
    try:
        snapshot = load_snapshot(config_dir, "local", TEST_ENV)
        dev = resolve(snapshot, ["eng-all", "payments-devs"])  # ceiling internal
        assert "payments-incidents" in dev.readable_sources  # config now allows it ...
        assert "payments-incidents" not in sources_seen(dev)  # ... rows still say confidential
    finally:
        source.write_text(original)


# --- through the MCP server ---------------------------------------------------------------------


@pytest.fixture
def knowledge_url(corpus, entra, store):
    port = free_port()
    auth = RemoteAuthProvider(
        token_verifier=entra.verifier(),
        authorization_servers=[entra_issuer(TENANT)],
        base_url=f"http://127.0.0.1:{port}",
    )
    pool = AsyncConnectionPool(db.db_conninfo("app"), min_size=1, max_size=4, open=False)
    server = build_server(store, auth, knowledge=Knowledge(pool, EMBEDDER))
    with serve(build_http_app(server, store), port) as url:
        yield url


async def ask(url, entra, groups, question):
    async with Client(f"{url}/mcp", auth=entra.token(groups=groups)) as c:
        return (await c.call_tool("search_knowledge", {"query": question, "k": 10})).data


async def test_search_knowledge_tool_per_user(knowledge_url, entra):
    question = "How do we roll back a deployment or retry a refund?"
    paul = await ask(knowledge_url, entra, [G_ENG_ALL, G_PAYMENTS_DEVS], question)
    ana = await ask(knowledge_url, entra, [G_ENG_ALL, G_PLATFORM_DEVS], question)
    lead = await ask(knowledge_url, entra, [G_ENG_ALL, G_PAYMENTS_LEADS], question)
    paul_sources = {r["source"] for r in paul["results"]}
    ana_sources = {r["source"] for r in ana["results"]}
    assert paul_sources <= {"eng-standards", "payments-code"} and "payments-code" in paul_sources
    assert ana_sources <= {"eng-standards", "platform-infra"} and "platform-infra" in ana_sources
    assert paul["max_classification"] == "internal" and lead["max_classification"] == "confidential"
    assert "payments-incidents" not in paul["searched_sources"]  # granted, above the ceiling
    assert "payments-incidents" in lead["searched_sources"]
    assert all(r["source"] != "payments-incidents" for r in paul["results"])


async def test_search_knowledge_needs_the_tool_grant(knowledge_url, entra):
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError, match="not granted"):  # signed-in basics only
        await ask(knowledge_url, entra, [], "anything")

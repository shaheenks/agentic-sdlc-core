"""Stage 6: knowledge graph under RLS, graph ingest (cache, failures, cleanup), graph_query.

Throwaway `sdlc_test` database (tests/support/db.py), hash embeddings and the deterministic
VocabularyExtractor. Run: uv run --env-file .env pytest tests/db
"""

import psycopg
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import RemoteAuthProvider
from psycopg_pool import AsyncConnectionPool
from sdlc_auth.entra import entra_issuer
from sdlc_config import load_snapshot, resolve
from sdlc_db import HashEmbedder, graph_search
from sdlc_mcp_bootstrap.knowledge_tools import Knowledge
from sdlc_mcp_bootstrap.server import build_http_app, build_server

from tests.support import db
from tests.support.config import make_config_dir
from tests.support.db import app_query, ingest_as_ingest_role, run, superuser_query
from tests.support.entra import G_ENG_ALL, G_PAYMENTS_DEVS, G_PLATFORM_DEVS, TENANT, TEST_ENV
from tests.support.graph import VocabularyExtractor
from tests.support.servers import free_port, serve

pytestmark = pytest.mark.skipif(bool(db.available()), reason=str(db.available()))

EMBEDDER = HashEmbedder()
PAYMENTS_DEV = ["eng-all", "payments-devs"]
PAYMENTS_LEAD = ["eng-all", "payments-leads"]
PLATFORM_DEV = ["eng-all", "platform-devs"]
ADMIN = ["platform-admins"]
GRAPH_TABLES = ("entities", "mentions", "edges")


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    db.create_test_database()
    config_dir = make_config_dir(tmp_path_factory.mktemp("repo"))
    snapshot = load_snapshot(config_dir, "local", TEST_ENV)
    extractor = VocabularyExtractor()
    reports = run(ingest_as_ingest_role(snapshot, config_dir.parent, EMBEDDER, extractor))
    return config_dir, snapshot, {r.source_id: r for r in reports}, extractor


def entity_sources(policy) -> dict[str, set[str]]:
    rows = app_query("SELECT source_id, key FROM entities", policy)
    out: dict[str, set[str]] = {}
    for source_id, key in rows:
        out.setdefault(source_id, set()).add(key)
    return out


# --- ingest --------------------------------------------------------------------------------------


def test_every_source_has_a_graph(corpus):
    _, _, reports, _ = corpus
    assert all(r.entities_written > 0 and not r.errors for r in reports.values()), reports
    per_source = dict(superuser_query("SELECT source_id, count(*) FROM edges GROUP BY 1"))
    assert set(per_source) >= {"payments-code", "platform-infra", "payments-incidents"}


def test_graph_rows_carry_the_source_classification(corpus):
    rows = superuser_query(
        "SELECT DISTINCT e.source_id, e.classification_rank = s.classification_rank"
        " FROM entities e JOIN sources s ON s.id = e.source_id"
    )
    assert rows and all(same for _, same in rows)


def test_extractions_are_cached(corpus):
    config_dir, snapshot, _, _ = corpus
    extractor = VocabularyExtractor()
    [report] = run(
        ingest_as_ingest_role(
            snapshot, config_dir.parent, EMBEDDER, extractor, ["payments-code"], force=True
        )
    )
    assert report.files_changed > 0 and report.extraction_calls == 0 and extractor.calls == 0
    assert report.entities_written > 0  # written again from the cache


def test_failed_extraction_skips_the_file_and_retries(corpus):
    config_dir, snapshot, _, _ = corpus
    folder = config_dir.parent / "samples/sources/platform-infra/docs"
    (folder / "new-service.md").write_text("# queue-service\n\nqueue-service runs on job-runner.\n")
    failing = VocabularyExtractor(fail_on="new-service.md")
    [report] = run(
        ingest_as_ingest_role(snapshot, config_dir.parent, EMBEDDER, failing, ["platform-infra"])
    )
    assert report.errors and "new-service.md" in report.errors[0]
    paths = {p for (p,) in superuser_query("SELECT path FROM documents")}
    assert "docs/new-service.md" not in paths  # not written: no hash recorded, so it is retried
    [retry] = run(
        ingest_as_ingest_role(
            snapshot, config_dir.parent, EMBEDDER, VocabularyExtractor(), ["platform-infra"]
        )
    )
    assert not retry.errors and retry.files_changed == 1
    (folder / "new-service.md").unlink()
    run(
        ingest_as_ingest_role(
            snapshot, config_dir.parent, EMBEDDER, VocabularyExtractor(), ["platform-infra"]
        )
    )


def test_deleted_files_drop_their_entities(corpus):
    config_dir, snapshot, _, _ = corpus
    incidents = config_dir.parent / "samples/sources/payments-incidents"
    moved = incidents / "INC-2044-ledger-posting-lag.md"
    text = moved.read_text(encoding="utf-8")
    moved.unlink()
    run(
        ingest_as_ingest_role(
            snapshot, config_dir.parent, EMBEDDER, VocabularyExtractor(), ["payments-incidents"]
        )
    )
    keys = {
        k
        for (k,) in superuser_query(
            "SELECT key FROM entities WHERE source_id = 'payments-incidents'"
        )
    }
    assert "inc-2044" not in keys and "inc-2031" in keys
    moved.write_text(text, encoding="utf-8")
    run(
        ingest_as_ingest_role(
            snapshot, config_dir.parent, EMBEDDER, VocabularyExtractor(), ["payments-incidents"]
        )
    )


# --- row-level security ---------------------------------------------------------------------------


def test_no_rls_context_means_no_graph_rows(corpus):
    for table in (*GRAPH_TABLES, "extraction_cache"):
        with psycopg.connect(db.db_conninfo("app")) as conn:
            if table == "extraction_cache":  # sdlc_app has no grant at all
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(f"SELECT count(*) FROM {table}")  # noqa: S608
            else:
                assert conn.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)  # noqa: S608


@pytest.mark.parametrize(
    ("groups", "expected"),
    [
        (PAYMENTS_DEV, {"eng-standards", "payments-code"}),
        (PAYMENTS_LEAD, {"eng-standards", "payments-code", "payments-incidents"}),
        (PLATFORM_DEV, {"eng-standards", "platform-infra"}),
        (ADMIN, {"eng-standards", "payments-code", "payments-incidents", "platform-infra"}),
    ],
)
def test_graph_rows_visible_per_persona(corpus, groups, expected):
    policy = resolve(corpus[1], groups)
    for table in GRAPH_TABLES:
        seen = {s for (s,) in app_query(f"SELECT DISTINCT source_id FROM {table}", policy)}  # noqa: S608
        assert seen <= expected, table
    assert set(entity_sources(policy)) == expected


def test_same_named_entities_join_only_across_readable_sources(corpus):
    """job-runner is named in payments-code and in platform-infra. A payments dev reaches the
    payments-code row only; an admin also reaches platform-infra through the same key."""
    snap = corpus[1]
    question = "Where does the refund-worker run?"
    [vec] = EMBEDDER.embed([question], "query")

    async def ask(groups):
        async with await psycopg.AsyncConnection.connect(db.db_conninfo("app")) as conn:
            return await graph_search(conn, resolve(snap, groups), vec, question, k=10, hops=1)

    dev, admin = run(ask(PAYMENTS_DEV)), run(ask(ADMIN))
    assert "job-runner" in {e.key for e in dev.entities}
    assert {e.source_id for e in dev.entities} <= {"eng-standards", "payments-code"}
    assert {h.source_id for h in dev.hits} <= {"eng-standards", "payments-code"}
    assert any(e.key == "job-runner" and e.source_id == "platform-infra" for e in admin.entities)
    assert "platform-infra" in {h.source_id for h in admin.hits}
    assert ("refund-worker", "runs_on", "job-runner") in {
        (e.source, e.relation, e.target) for e in dev.edges
    }


def test_graph_search_returns_one_chunk_per_document(corpus):
    snap = corpus[1]
    question = "INC-2031 duplicate refunds root cause and actions"
    [vec] = EMBEDDER.embed([question], "query")

    async def ask():
        async with await psycopg.AsyncConnection.connect(db.db_conninfo("app")) as conn:
            return await graph_search(conn, resolve(snap, ADMIN), vec, question, k=10)

    hits = run(ask()).hits
    docs = [(h.source_id, h.path) for h in hits]
    assert len(docs) == len(set(docs))


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


async def graph(url, entra, groups, question, hops=1):
    async with Client(f"{url}/mcp", auth=entra.token(groups=groups)) as c:
        return (await c.call_tool("graph_query", {"query": question, "k": 8, "hops": hops})).data


async def test_graph_query_tool_per_user(knowledge_url, entra):
    question = "Which service does the refund-worker run on and who owns it?"
    paul = await graph(knowledge_url, entra, [G_ENG_ALL, G_PAYMENTS_DEVS], question)
    ana = await graph(knowledge_url, entra, [G_ENG_ALL, G_PLATFORM_DEVS], question)
    assert {r["source"] for r in paul["results"]} <= {"eng-standards", "payments-code"}
    assert {e["source"] for e in paul["entities"]} <= {"eng-standards", "payments-code"}
    assert {r["from"] for r in paul["relations"]} and all(
        r["source"] in {"eng-standards", "payments-code"} for r in paul["relations"]
    )
    assert {r["source"] for r in ana["results"]} <= {"eng-standards", "platform-infra"}
    assert all(e["source"] != "payments-code" for e in ana["entities"])
    assert paul["results"] and all(r["via"] in {"vector", "graph"} for r in paul["results"])


async def test_graph_query_needs_the_developer_role(knowledge_url, entra):
    with pytest.raises(ToolError, match="not granted"):  # viewer: search_knowledge only
        await graph(knowledge_url, entra, [G_ENG_ALL], "anything")

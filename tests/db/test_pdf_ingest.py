"""H10: PDFs end to end on a throwaway Postgres: stored with their media type, searchable with page
citations, still filtered by RLS; the MCP tools return `pages` for PDF hits."""

import psycopg
import pytest
from fastmcp import Client
from fastmcp.server.auth import RemoteAuthProvider
from psycopg_pool import AsyncConnectionPool
from sdlc_auth.entra import entra_issuer
from sdlc_config import load_snapshot, resolve
from sdlc_db import HashEmbedder, search
from sdlc_mcp_bootstrap.knowledge_tools import Knowledge
from sdlc_mcp_bootstrap.server import build_http_app, build_server

from tests.support import db
from tests.support.config import make_config_dir
from tests.support.db import app_query, ingest_as_ingest_role, run, superuser_query
from tests.support.entra import G_ENG_ALL, G_PAYMENTS_DEVS, TENANT, TEST_ENV
from tests.support.graph import VocabularyExtractor
from tests.support.servers import free_port, serve

pytestmark = pytest.mark.skipif(bool(db.available()), reason=str(db.available()))

EMBEDDER = HashEmbedder()
POLICY_PDF = "incident-policy.pdf"
SCAN_PDF = "docs/change-freeze-notice.pdf"
QUESTION = "SEV1 incident commander paged within 5 minutes status page within 30 minutes"


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    db.create_test_database()
    config_dir = make_config_dir(tmp_path_factory.mktemp("repo"))
    snapshot = load_snapshot(config_dir, "local", TEST_ENV)
    reports = run(
        ingest_as_ingest_role(snapshot, config_dir.parent, EMBEDDER, VocabularyExtractor())
    )
    return snapshot, {r.source_id: r for r in reports}


def test_pdfs_are_stored_with_their_media_type(corpus):
    _, reports = corpus
    rows = dict(
        superuser_query(
            "SELECT d.path, d.media_type FROM documents d WHERE d.path IN (%s, %s)",
            (POLICY_PDF, SCAN_PDF),
        )
    )
    assert rows == {POLICY_PDF: "application/pdf", SCAN_PDF: "application/pdf"}
    # the scan has no text layer and OCR is not used in tests: recorded, but without chunks
    [(scan_chunks,)] = superuser_query(
        "SELECT count(*) FROM chunks c JOIN documents d ON d.id = c.document_id WHERE d.path = %s",
        (SCAN_PDF,),
    )
    assert scan_chunks == 0
    assert reports["platform-infra"].pdf_pages_without_text == 1
    assert reports["eng-standards"].pdf_pages == 3


def test_pdf_chunks_carry_pages_and_bookmark_headings(corpus):
    rows = superuser_query(
        "SELECT c.start_line, c.end_line, c.heading FROM chunks c"
        " JOIN documents d ON d.id = c.document_id WHERE d.path = %s ORDER BY c.ordinal",
        (POLICY_PDF,),
    )
    assert ("3 Response > 3.1 Escalation matrix") in {heading for _, _, heading in rows}
    assert {start for start, _, _ in rows} == {1, 2, 3}  # pages, not lines


def test_search_returns_the_pdf_page(corpus):
    snapshot, _ = corpus

    async def go():
        async with await psycopg.AsyncConnection.connect(db.db_conninfo("app")) as conn:
            [vec] = EMBEDDER.embed([QUESTION], "query")
            return await search(conn, resolve(snapshot, ["eng-all"]), vec, k=5)

    hits = run(go())
    pdf_hits = [h for h in hits if h.path == POLICY_PDF]
    assert pdf_hits and pdf_hits[0].is_pdf and pdf_hits[0].start_line == 2  # page 2


def test_rls_applies_to_pdfs(corpus):
    snapshot, _ = corpus
    dev = resolve(snapshot, ["eng-all", "payments-devs"])  # no platform-infra access
    paths = {p for (p,) in app_query("SELECT path FROM documents", dev)}
    assert POLICY_PDF in paths and SCAN_PDF not in paths


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


async def test_search_knowledge_cites_pages_for_pdfs(knowledge_url, entra):
    async with Client(
        f"{knowledge_url}/mcp", auth=entra.token(groups=[G_ENG_ALL, G_PAYMENTS_DEVS])
    ) as c:
        result = (await c.call_tool("search_knowledge", {"query": QUESTION, "k": 10})).data
    pdf = [r for r in result["results"] if r["path"] == POLICY_PDF]
    text = [r for r in result["results"] if not r["path"].endswith(".pdf")]
    assert pdf and pdf[0]["pages"] == [2, 2] and "lines" not in pdf[0]
    assert text and "lines" in text[0] and "pages" not in text[0]

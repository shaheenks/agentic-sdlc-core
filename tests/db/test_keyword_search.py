"""version-03 P11 (K1): keyword (full-text) search fused with vector search, under RLS.

Throwaway `sdlc_test` database (tests/support/db.py), sample corpus, hash embeddings.
    uv run --env-file .env pytest tests/db/test_keyword_search.py
"""

import psycopg
import pytest
from sdlc_config import load_snapshot, resolve
from sdlc_db import HashEmbedder, graph_search, search

from tests.support import db
from tests.support.config import make_config_dir
from tests.support.db import app_query, ingest_as_ingest_role, run, superuser_query
from tests.support.entra import TEST_ENV
from tests.support.graph import VocabularyExtractor

pytestmark = pytest.mark.skipif(bool(db.available()), reason=str(db.available()))

EMBEDDER = HashEmbedder()
PAYMENTS_DEV = ["SDLC.User", "SDLC.Payments.Member"]
PAYMENTS_LEAD = ["SDLC.User", "SDLC.Payments.Approver"]
PLATFORM_DEV = ["SDLC.User", "SDLC.Platform.Member"]
# a query vector that matches nothing in particular: only the keyword ranking can find the chunk
UNRELATED = EMBEDDER.embed(["zebra quartz violin"], "query")[0]


@pytest.fixture(scope="module")
def snap(tmp_path_factory):
    db.create_test_database()
    config_dir = make_config_dir(tmp_path_factory.mktemp("repo"))
    snapshot = load_snapshot(config_dir, "local", TEST_ENV)
    run(ingest_as_ingest_role(snapshot, config_dir.parent, EMBEDDER, VocabularyExtractor()))
    return snapshot


async def _search(snap, groups, query, vec=UNRELATED, keyword=True, k=5):
    async with await psycopg.AsyncConnection.connect(db.db_conninfo("app")) as conn:
        return await search(conn, resolve(snap, groups), vec, k, query=query, keyword=keyword)


async def _graph(snap, groups, query, vec=UNRELATED, keyword=True):
    async with await psycopg.AsyncConnection.connect(db.db_conninfo("app")) as conn:
        return await graph_search(conn, resolve(snap, groups), vec, query, 5, 1, keyword=keyword)


def test_generated_column_is_filled_by_ingest(snap):
    [(empty,)] = superuser_query("SELECT count(*) FROM chunks WHERE content_tsv IS NULL")
    assert empty == 0
    # identifiers stay whole in the simple config
    [(found,)] = superuser_query(
        "SELECT count(*) FROM chunks WHERE content_tsv @@ to_tsquery('simple', %s)",
        ("'refund_manual_review'",),
    )
    assert found >= 1


def test_exact_token_found_where_vector_only_misses(snap):
    query = "what happens with refund_manual_review"
    vector_only = run(_search(snap, PAYMENTS_DEV, query, keyword=False))
    fused = run(_search(snap, PAYMENTS_DEV, query))
    assert not any(h.path.endswith("refunds.md") for h in vector_only[:1])
    assert fused[0].path.endswith("refunds.md") and fused[0].via in ("keyword", "both")
    assert "refund_manual_review" in fused[0].content


def test_keyword_hits_only_from_readable_sources(snap):
    # payments-code is not readable for a platform developer: its exact token never matches
    hits = run(_search(snap, PLATFORM_DEV, "refund_manual_review"))
    assert all(h.source_id != "payments-code" for h in hits)
    assert not [h for h in hits if h.via in ("keyword", "both")]
    # and the lead reads incidents (confidential), the developer does not
    lead = run(_search(snap, PAYMENTS_LEAD, "INC-2031"))
    dev = run(_search(snap, PAYMENTS_DEV, "INC-2031"))
    assert any(h.source_id == "payments-incidents" and h.via != "vector" for h in lead)
    assert all(h.source_id != "payments-incidents" for h in dev)


def test_fusion_is_deterministic_and_off_means_vector_only(snap):
    query = "point_in_time_recovery_enabled backups"
    first = run(_search(snap, ["SDLC.Admin"], query))
    again = run(_search(snap, ["SDLC.Admin"], query))
    assert [(h.source_id, h.path, h.start_line) for h in first] == [
        (h.source_id, h.path, h.start_line) for h in again
    ]
    assert any(h.path.endswith("cloudsql.tf") for h in first)
    off = run(_search(snap, ["SDLC.Admin"], query, keyword=False))
    assert {h.via for h in off} == {"vector"}


def test_graph_query_starts_from_keyword_hits(snap):
    found = run(_graph(snap, PAYMENTS_LEAD, "INC-2031 timeline"))
    assert any(h.source_id == "payments-incidents" for h in found.hits)
    assert any(h.via in ("keyword", "both", "graph") for h in found.hits)
    off = run(_graph(snap, PAYMENTS_LEAD, "INC-2031 timeline", keyword=False))
    assert not any(h.via in ("keyword", "both") for h in off.hits)


def test_no_rls_context_still_no_rows(snap):
    assert app_query(
        "SELECT count(*) FROM chunks WHERE content_tsv @@ to_tsquery('simple', 'refund')"
    ) == [(0,)]


def test_missing_column_falls_back_to_vector(snap):
    """keyword_search on before migration 007 reached the database: vector results, no error."""
    db.superuser_query("SELECT 1")  # connection check
    with psycopg.connect(db._superuser(db.TEST_DB), autocommit=True) as conn:
        conn.execute("ALTER TABLE sdlc.chunks RENAME COLUMN content_tsv TO content_tsv_off")
    try:
        hits = run(_search(snap, PAYMENTS_DEV, "refund_manual_review"))
        assert hits and {h.via for h in hits} == {"vector"}
    finally:
        with psycopg.connect(db._superuser(db.TEST_DB), autocommit=True) as conn:
            conn.execute("ALTER TABLE sdlc.chunks RENAME COLUMN content_tsv_off TO content_tsv")

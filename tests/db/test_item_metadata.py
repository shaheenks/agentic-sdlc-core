"""version-01 M0 on a real Postgres: item metadata (title, url), sync_state cursors, restricted
items and deletions through `all_ids()` for incremental loaders. A fake incremental loader
stands in for the remote connectors (M1-M4).

Needs the Postgres container and .env passwords:  uv run --env-file .env pytest tests/db
"""

import hashlib
from dataclasses import replace

import psycopg
import pytest
from sdlc_config import load_snapshot, resolve
from sdlc_db import HashEmbedder, search
from sdlc_loaders import LOADERS, Loader, LoaderError, SourceItem

from tests.support import db
from tests.support.config import make_config_dir
from tests.support.db import ingest_as_ingest_role, run, superuser_query
from tests.support.entra import TEST_ENV

pytestmark = pytest.mark.skipif(bool(db.available()), reason=str(db.available()))

EMBEDDER = HashEmbedder()
SOURCE = "fake-remote"
BASE = "https://acme.atlassian.net/wiki/spaces/ENG/pages"


def item(path, text, title=None, restricted=False):
    return SourceItem(
        path=path,
        text=text,
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
        media_type="text/markdown",
        title=title,
        url=f"{BASE}/{path}" if title else None,
        restricted=restricted,
    )


class FakeLoader(Loader):
    """Yields the scripted items for this run; records the cursor it was given."""

    incremental = True
    script: dict = {}
    received: list = []

    def items(self, cursor=None):
        FakeLoader.received.append(cursor)
        yield from self.script["items"]
        self.cursor = self.script.get("cursor")

    def all_ids(self):
        ids = self.script["ids"]
        if isinstance(ids, Exception):
            raise ids
        return set(ids)


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    db.create_test_database()
    config_dir = make_config_dir(tmp_path_factory.mktemp("repo"))
    snapshot = load_snapshot(config_dir, "local", TEST_ENV)
    fake = replace(snapshot.sources["eng-standards"], id=SOURCE, type="fake", source="fake")
    snapshot = replace(snapshot, sources={**snapshot.sources, SOURCE: fake})
    LOADERS["fake"] = lambda source, repo_root, cache_root, secrets: FakeLoader()
    yield config_dir, snapshot
    LOADERS.pop("fake", None)


def ingest(env, items, ids, cursor=None):
    config_dir, snapshot = env
    FakeLoader.script = {"items": items, "ids": ids, "cursor": cursor}
    [report] = run(ingest_as_ingest_role(snapshot, config_dir.parent, EMBEDDER, None, [SOURCE]))
    return report


def stored():
    rows = superuser_query(
        "SELECT path, title, url FROM documents WHERE source_id = %s ORDER BY path", (SOURCE,)
    )
    return {path: (title, url) for path, title, url in rows}


def cursor():
    rows = superuser_query("SELECT cursor FROM sync_state WHERE source_id = %s", (SOURCE,))
    return rows[0][0] if rows else None


def test_incremental_lifecycle(env):
    # run 1: first sync. B is natively restricted: never written.
    r1 = ingest(
        env,
        [item("A", "# Alpha\nalpha text", "Page A"), item("B", "# B", "B", True), item("C", "c")],
        {"A", "B", "C"},
        {"updated_since": "t1"},
    )
    assert (r1.files_changed, r1.files_restricted, r1.errors) == (2, 1, [])
    assert stored() == {"A": ("Page A", f"{BASE}/A"), "C": (None, None)}
    assert cursor() == {"updated_since": "t1"}
    assert FakeLoader.received[-1] is None  # nothing stored yet

    # run 2: resumes from the cursor; A renamed (same content) -> metadata only; C gone
    r2 = ingest(
        env, [item("A", "# Alpha\nalpha text", "Page A (renamed)")], {"A"}, {"updated_since": "t2"}
    )
    assert FakeLoader.received[-1] == {"updated_since": "t1"}
    assert (r2.files_changed, r2.metadata_updated, r2.files_deleted) == (0, 1, 1)
    assert stored() == {"A": ("Page A (renamed)", f"{BASE}/A")}
    assert cursor() == {"updated_since": "t2"}

    # run 3: listing ids fails -> nothing deleted, cursor kept for a retry
    r3 = ingest(env, [], LoaderError("listing failed"), {"updated_since": "t3"})
    assert r3.errors and r3.files_deleted == 0
    assert stored() == {"A": ("Page A (renamed)", f"{BASE}/A")}
    assert cursor() == {"updated_since": "t2"}

    # run 4: A became restricted at the source -> its stored copy is deleted
    r4 = ingest(env, [item("A", "# Alpha\nalpha text", "Page A", True)], {"A"}, None)
    assert (r4.files_restricted, r4.files_deleted) == (1, 1)
    assert stored() == {}
    assert cursor() is None  # loader returned no cursor: state cleared


def test_search_returns_title_and_url(env):
    config_dir, snapshot = env
    ingest(env, [item("D", "# Delta runbook\nrestart the delta service", "Delta runbook")], {"D"})
    policy = resolve(snapshot, ["eng-all"])
    assert SOURCE in policy.readable_sources
    [vector] = EMBEDDER.embed(["# Delta runbook\nrestart the delta service"], "query")

    async def query():
        async with await psycopg.AsyncConnection.connect(db.db_conninfo("app")) as conn:
            return await search(conn, policy, vector, 20)

    hits = [h for h in run(query()) if h.source_id == SOURCE]
    assert hits and (hits[0].title, hits[0].url) == ("Delta runbook", f"{BASE}/D")


def test_sync_state_is_ingest_only(env):
    with psycopg.connect(db.db_conninfo("app")) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT count(*) FROM sync_state")
    with psycopg.connect(db.db_conninfo("owner")) as conn:  # forced RLS: owner sees nothing
        assert conn.execute("SELECT count(*) FROM sync_state").fetchone() == (0,)

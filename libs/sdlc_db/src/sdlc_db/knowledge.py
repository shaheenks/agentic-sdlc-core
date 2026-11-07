"""Knowledge queries (MCP server, RLS-scoped) and ingest writes (sdlc_ingest role)."""

import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from psycopg import AsyncConnection, errors
from sdlc_config import EffectivePolicy, Snapshot

from sdlc_db.scoped import scoped

if TYPE_CHECKING:
    from sdlc_db.graph import Extraction, GraphCounts

log = logging.getLogger("sdlc.db")

# Tables whose rows carry source_id + classification_rank (re-stamped when a source's
# classification changes). Keep in sync with db/migrations.
CLASSIFIED_TABLES = ("documents", "chunks", "entities", "mentions", "edges")


def vector_literal(values: Sequence[float]) -> str:
    return "[" + ",".join(f"{float(v):.7g}" for v in values) + "]"


@dataclass(frozen=True)
class SearchHit:
    source_id: str
    path: str
    start_line: int
    end_line: int
    heading: str | None
    content: str
    score: float  # cosine similarity, 1 = identical (graph_search: plus graph/glossary bonus)
    # "vector" | "keyword" | "both" (found by both rankings, P11) | "graph" (via the graph)
    via: str = "vector"
    media_type: str = "text/plain"  # application/pdf: start_line/end_line are page numbers
    title: str | None = None  # item title in its source system (version-01 M0)
    url: str | None = None  # deep link to the item (version-01 M0)

    @property
    def is_pdf(self) -> bool:
        return self.media_type == "application/pdf"


# --- keyword search (version-03 P11) ----------------------------------------------------------
# chunks.content_tsv is a `simple`-config tsvector (migration 007): identifiers stay whole.

TS_CONFIG = "simple"
KEYWORD_CANDIDATES = 20  # chunks taken from each ranking before fusion
FUSION_CANDIDATES = 20  # vector chunks considered when keyword search is on
RRF_K = 60  # reciprocal rank fusion: score = sum of 1 / (RRF_K + rank)
MAX_TERMS = 12
# K2 eval (2026-11-07): plain words made the keyword ranking noisy and cost prose questions; only
# identifier-like terms are searched, prose stays with the vector ranking
KEYWORD_PLAIN_WORDS = False
# identifiers keep _ . - / inside; ":" is left out (tsquery syntax)
_TOKEN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_./-]*[A-Za-z0-9])?")
# common question words: the simple config keeps every word, so plain prose terms would match
# almost every chunk; prose is covered by the vector ranking
_STOP = frozenset(
    """about after also been before being both could does doing done each from have having here
    into just like many more most much must need only other over same should show some such than
    that their them then there these they this those through under used uses using very want what
    when where which while will with would your""".split()
)

# row layout of both queries: 0 id, 1 source_id, 2 path, 3 start_line, 4 end_line, 5 heading,
# 6 content, 7 cosine score, 8 media_type, 9 title, 10 url
_SEARCH_COLUMNS = """c.id, c.source_id, d.path, c.start_line, c.end_line, c.heading, c.content,
                     1 - (c.embedding <=> %(vec)s::vector) AS score, d.media_type, d.title, d.url"""


def keyword_terms(query: str) -> list[str]:
    """Distinctive terms of a question: identifiers (digits, `_ . - /`, camelCase) and words
    of 4+ letters that are not common question words. Lower case, in order, at most MAX_TERMS.
    Plain acronyms (MCP, GCP, PCI) are not identifiers: they are everywhere in a corpus about
    them, and as graph seeds they pushed the right files out (K2 on GCP dev, 2026-11-07)."""
    terms: list[str] = []
    for token in _TOKEN.findall(query or ""):
        identifier = (
            any(c in token for c in "_.-/")
            or any(c.isdigit() for c in token)
            or (token[1:] != token[1:].lower() and token != token.upper())  # camelCase
        )
        word = token.lower()
        if identifier or (KEYWORD_PLAIN_WORDS and len(word) >= 4 and word not in _STOP):
            terms.append(word)
    return list(dict.fromkeys(terms))[:MAX_TERMS]


def tsquery_text(terms: Sequence[str]) -> str:
    """`'a' | 'b'` for to_tsquery: any term matches; Postgres splits each term with the same
    parser as the documents (so `refund_manual_review` becomes a phrase of its parts). Terms only
    hold [a-z0-9_./-], so quoting is safe."""
    return " | ".join(f"'{t}'" for t in terms if _TOKEN.fullmatch(t))


# keyword match bonus, added to the cosine similarity: rank 1 = KEYWORD_BONUS, halved by rank 11
KEYWORD_BONUS = 0.08
KEYWORD_DECAY = 10


def keyword_bonus(rank: int | None) -> float:
    return 0.0 if rank is None else KEYWORD_BONUS * KEYWORD_DECAY / (KEYWORD_DECAY + rank - 1)


def fuse(*rankings: Sequence[int]) -> list[tuple[int, float, tuple[int, ...]]]:
    """Reciprocal rank fusion of id rankings: (id, score, the rankings it appeared in), best
    first; ties by best single rank, then id (deterministic)."""
    scores: dict[int, float] = {}
    seen_in: dict[int, list[int]] = {}
    best: dict[int, int] = {}
    for which, ranking in enumerate(rankings):
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (RRF_K + rank)
            seen_in.setdefault(item, []).append(which)
            best[item] = min(best.get(item, rank), rank)
    order = sorted(scores, key=lambda i: (-scores[i], best[i], i))
    return [(i, scores[i], tuple(seen_in[i])) for i in order]


async def keyword_rows(conn: AsyncConnection, vec: str, terms: Sequence[str], n: int) -> list:
    """Best keyword matches (inside an open scoped() transaction: RLS applies)."""
    text = tsquery_text(terms)
    if not text:
        return []
    try:
        async with conn.transaction():  # savepoint: a failure leaves the vector results usable
            return await _keyword_query(conn, vec, text, n)
    except errors.UndefinedColumn:  # migration 007 not applied yet: vector only, say so
        log.warning("keyword search unavailable: chunks.content_tsv missing (run migrations)")
        return []


async def _keyword_query(conn: AsyncConnection, vec: str, text: str, n: int) -> list:
    cur = await conn.execute(
        f"""
        SELECT {_SEARCH_COLUMNS}
        FROM chunks c JOIN documents d ON d.id = c.document_id,
             to_tsquery(%(cfg)s::regconfig, %(q)s) AS q
        WHERE c.content_tsv @@ q
        ORDER BY ts_rank_cd(c.content_tsv, q) DESC, c.id
        LIMIT %(n)s
        """,  # noqa: S608 (constant column list)
        {"vec": vec, "cfg": TS_CONFIG, "q": text, "n": n},
    )
    return await cur.fetchall()


def via_label(found_in: tuple[int, ...]) -> str:
    return "both" if len(found_in) > 1 else ("vector" if found_in == (0,) else "keyword")


def _hit(row, via: str) -> SearchHit:
    return SearchHit(
        *row[1:7], score=float(row[7]), via=via, media_type=row[8], title=row[9], url=row[10]
    )


async def search(
    conn: AsyncConnection,
    policy: EffectivePolicy,
    embedding: Sequence[float],
    k: int = 5,
    query: str | None = None,
    keyword: bool = False,
) -> list[SearchHit]:
    """Nearest chunks the caller may read (RLS filters by source and classification). With
    `keyword` and a `query`, chunks matching the query's identifier terms join the vector
    candidates and get a rank bonus on top of their cosine similarity (`score` stays the cosine
    similarity); `via` says which search found the chunk. graph_query uses the same bonus and
    takes its walk's starting points from the RRF-fused list."""
    k = max(1, min(int(k), 20))
    vec = vector_literal(embedding)
    terms = keyword_terms(query or "") if keyword else []
    async with scoped(conn, policy):
        # With RLS filtering after the index scan, let HNSW keep scanning until k rows qualify.
        await conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
        await conn.execute("SET LOCAL hnsw.ef_search = 100")
        cur = await conn.execute(
            f"""SELECT {_SEARCH_COLUMNS} FROM chunks c JOIN documents d ON d.id = c.document_id
                ORDER BY c.embedding <=> %(vec)s::vector LIMIT %(n)s""",  # noqa: S608
            {"vec": vec, "n": max(k, FUSION_CANDIDATES) if terms else k},
        )
        vector = await cur.fetchall()
        matches = await keyword_rows(conn, vec, terms, KEYWORD_CANDIDATES) if terms else []
    if not matches:
        return [_hit(row, "vector") for row in vector[:k]]
    # K2 eval: equal-weight rank fusion let keyword noise push out good vector hits; a bonus on
    # top of the cosine similarity (as graph_query does) keeps vector order unless a chunk
    # matches the exact terms
    rows = {row[0]: row for row in vector + matches}
    in_vector = {row[0] for row in vector}
    rank = {row[0]: n for n, row in enumerate(matches, start=1)}

    def ranked(chunk_id: int) -> tuple[float, int]:
        return (-(float(rows[chunk_id][7]) + keyword_bonus(rank.get(chunk_id))), chunk_id)

    order = sorted(rows, key=ranked)[:k]
    return [
        _hit(
            rows[i],
            "both" if i in in_vector and i in rank else "keyword" if i in rank else "vector",
        )
        for i in order
    ]


# --- ingest (sdlc_ingest role; its policy sees every row) ------------------------------------


async def sync_sources(conn: AsyncConnection, snapshot: Snapshot) -> tuple[int, list[str]]:
    """Upsert the sources registry from config; drop sources removed from config (cascade)."""
    async with conn.transaction():
        for s in snapshot.sources.values():
            await conn.execute(
                """
                INSERT INTO sources (id, classification, classification_rank, owner_team,
                                     config_version, updated_at)
                VALUES (%s, %s, %s, %s, %s, now())
                ON CONFLICT (id) DO UPDATE SET
                    classification = EXCLUDED.classification,
                    classification_rank = EXCLUDED.classification_rank,
                    owner_team = EXCLUDED.owner_team,
                    config_version = EXCLUDED.config_version,
                    updated_at = now()
                """,
                (s.id, s.classification, s.classification_rank, s.owner_team, snapshot.version),
            )
            # a classification change applies to already-ingested rows too
            for table in CLASSIFIED_TABLES:
                await conn.execute(
                    f"UPDATE {table} SET classification_rank = %s"  # noqa: S608 (constant names)
                    " WHERE source_id = %s AND classification_rank <> %s",
                    (s.classification_rank, s.id, s.classification_rank),
                )
        cur = await conn.execute(
            "DELETE FROM sources WHERE NOT (id = ANY(%s)) RETURNING id", (list(snapshot.sources),)
        )
        removed = [row[0] for row in await cur.fetchall()]
    return len(snapshot.sources), removed


async def document_hashes(conn: AsyncConnection, source_id: str) -> dict[str, str]:
    cur = await conn.execute(
        "SELECT path, content_hash FROM documents WHERE source_id = %s", (source_id,)
    )
    return {path: digest for path, digest in await cur.fetchall()}


@dataclass(frozen=True)
class StoredDocument:
    content_hash: str
    title: str | None
    url: str | None


async def stored_documents(conn: AsyncConnection, source_id: str) -> dict[str, StoredDocument]:
    """path -> what is stored, to skip unchanged items and refresh changed metadata only."""
    cur = await conn.execute(
        "SELECT path, content_hash, title, url FROM documents WHERE source_id = %s", (source_id,)
    )
    return {path: StoredDocument(h, t, u) for path, h, t, u in await cur.fetchall()}


async def update_document_metadata(
    conn: AsyncConnection, source_id: str, path: str, title: str | None, url: str | None
) -> None:
    """Title/URL changed but the content did not (e.g. a renamed page): no re-embedding."""
    await conn.execute(
        "UPDATE documents SET title = %s, url = %s WHERE source_id = %s AND path = %s",
        (title, url, source_id, path),
    )


async def get_sync_cursor(conn: AsyncConnection, source_id: str) -> dict[str, Any] | None:
    cur = await conn.execute("SELECT cursor FROM sync_state WHERE source_id = %s", (source_id,))
    row = await cur.fetchone()
    return row[0] if row else None


async def set_sync_cursor(
    conn: AsyncConnection, source_id: str, cursor: Mapping[str, Any] | None
) -> None:
    """Store (or, with None, clear) the cursor an incremental loader resumes from."""
    if cursor is None:
        await conn.execute("DELETE FROM sync_state WHERE source_id = %s", (source_id,))
        return
    await conn.execute(
        """
        INSERT INTO sync_state (source_id, cursor, last_synced_at) VALUES (%s, %s::jsonb, now())
        ON CONFLICT (source_id) DO UPDATE SET cursor = EXCLUDED.cursor, last_synced_at = now()
        """,
        (source_id, json.dumps(dict(cursor), sort_keys=True)),
    )


@dataclass(frozen=True)
class ChunkRow:
    ordinal: int
    start_line: int
    end_line: int
    heading: str | None
    content: str
    embedding: Sequence[float]


async def replace_document(
    conn: AsyncConnection,
    source_id: str,
    classification_rank: int,
    path: str,
    content_hash: str,
    chunks: Sequence[ChunkRow],
    embedding_model: str,
    graph: "Sequence[Extraction] | None" = None,
    media_type: str = "text/plain",
    title: str | None = None,
    url: str | None = None,
) -> "GraphCounts | None":
    """Replace one document, its chunks and (when `graph` is given, one Extraction per chunk)
    its graph mentions/edges atomically. Returns the graph counts, or None without a graph."""
    from sdlc_db.graph import drop_orphan_entities, write_graph

    chunk_ids: list[int] = []
    async with conn.transaction():
        await conn.execute(
            "DELETE FROM documents WHERE source_id = %s AND path = %s", (source_id, path)
        )
        cur = await conn.execute(
            """
            INSERT INTO documents (source_id, path, content_hash, classification_rank, media_type,
                                   title, url)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (source_id, path, content_hash, classification_rank, media_type, title, url),
        )
        (document_id,) = await cur.fetchone()
        for chunk in chunks:
            cur = await conn.execute(
                """
                INSERT INTO chunks (document_id, source_id, classification_rank, ordinal,
                                    start_line, end_line, heading, content, embedding,
                                    embedding_model)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s)
                RETURNING id
                """,
                (
                    document_id,
                    source_id,
                    classification_rank,
                    chunk.ordinal,
                    chunk.start_line,
                    chunk.end_line,
                    chunk.heading,
                    chunk.content,
                    vector_literal(chunk.embedding),
                    embedding_model,
                ),
            )
            chunk_ids.append((await cur.fetchone())[0])
        counts = None
        if graph is not None:
            counts = await write_graph(conn, source_id, classification_rank, chunk_ids, graph)
        await drop_orphan_entities(conn, source_id)
    return counts


async def delete_documents(conn: AsyncConnection, source_id: str, paths: Sequence[str]) -> int:
    if not paths:
        return 0
    from sdlc_db.graph import drop_orphan_entities

    async with conn.transaction():
        cur = await conn.execute(
            "DELETE FROM documents WHERE source_id = %s AND path = ANY(%s)",
            (source_id, list(paths)),
        )
        await drop_orphan_entities(conn, source_id)
    return cur.rowcount

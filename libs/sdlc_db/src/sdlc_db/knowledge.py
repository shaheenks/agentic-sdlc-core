"""Knowledge queries (MCP server, RLS-scoped) and ingest writes (sdlc_ingest role)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from psycopg import AsyncConnection
from sdlc_config import EffectivePolicy, Snapshot

from sdlc_db.scoped import scoped

if TYPE_CHECKING:
    from sdlc_db.graph import Extraction, GraphCounts

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
    via: str = "vector"  # "vector" | "graph" (reached through the knowledge graph)


async def search(
    conn: AsyncConnection, policy: EffectivePolicy, embedding: Sequence[float], k: int = 5
) -> list[SearchHit]:
    """Nearest chunks the caller may read (RLS filters by source and classification)."""
    k = max(1, min(int(k), 20))
    vec = vector_literal(embedding)
    async with scoped(conn, policy):
        # With RLS filtering after the index scan, let HNSW keep scanning until k rows qualify.
        await conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
        await conn.execute("SET LOCAL hnsw.ef_search = 100")
        cur = await conn.execute(
            """
            SELECT c.source_id, d.path, c.start_line, c.end_line, c.heading, c.content,
                   1 - (c.embedding <=> %s::vector) AS score
            FROM chunks c JOIN documents d ON d.id = c.document_id
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
            """,
            (vec, vec, k),
        )
        rows = await cur.fetchall()
    return [SearchHit(*row[:6], score=float(row[6])) for row in rows]


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
            INSERT INTO documents (source_id, path, content_hash, classification_rank)
            VALUES (%s, %s, %s, %s) RETURNING id
            """,
            (source_id, path, content_hash, classification_rank),
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

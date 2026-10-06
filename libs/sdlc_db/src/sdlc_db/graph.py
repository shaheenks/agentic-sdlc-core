"""Knowledge graph: ingest writes (sdlc_ingest) and hybrid retrieval (sdlc_app, RLS-scoped).

Per-source graph: entities/edges belong to one source; the same thing named in two sources shares
a `key` (normalized name). Traversal walks keys, so it crosses sources only where the caller can
read both sides: RLS hides the other rows, and with them the connection.

graph_search: vector seed -> entities in the best chunks + entities named in the question ->
1-2 hops over edges (recursive CTE, by key) -> chunks mentioning the reached entities, ranked by
vector similarity plus a graph bonus (closer = larger) and a small team-glossary boost.
"""

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb
from sdlc_config import EffectivePolicy

from sdlc_db.knowledge import SearchHit, vector_literal
from sdlc_db.scoped import scoped

MAX_HOPS = 2
VECTOR_CANDIDATES = 20  # nearest chunks considered before re-ranking
SEED_CHUNKS = 3  # entities mentioned in the best chunks seed the walk
MAX_KEYS = 40  # cap on reached entity keys (hub entities fan out quickly)
GRAPH_BONUS = {0: 0.06, 1: 0.04, 2: 0.02}  # added to cosine similarity by walk depth
GLOSSARY_BOOST = 0.03  # chunks from the caller's teams' glossary_source
MAX_EDGES = 60
MAX_PER_DOCUMENT = 1  # results are documents: the best chunk of each, so one file can't fill k


def entity_key(name: str) -> str:
    """'Refund Worker', 'refund_worker', '`refund-worker`', 'RefundWorker' -> 'refund-worker'."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", name.strip())
    return re.sub(r"[^a-z0-9]+", "-", spaced.lower()).strip("-")


# --- extraction results -------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtractedEntity:
    name: str
    type: str
    description: str = ""


@dataclass(frozen=True)
class ExtractedRelation:
    source: str  # entity name (subject)
    relation: str
    target: str  # entity name (object)


@dataclass(frozen=True)
class Extraction:
    entities: tuple[ExtractedEntity, ...] = ()
    relations: tuple[ExtractedRelation, ...] = ()

    def to_json(self) -> dict:
        return {
            "entities": [e.__dict__ for e in self.entities],
            "relations": [r.__dict__ for r in self.relations],
        }

    @classmethod
    def from_json(cls, data: Mapping) -> "Extraction":
        return cls(
            tuple(ExtractedEntity(**e) for e in data.get("entities", [])),
            tuple(ExtractedRelation(**r) for r in data.get("relations", [])),
        )

    def cleaned(
        self, entity_types: Iterable[str], relation_types: Iterable[str], max_entities: int = 25
    ) -> "Extraction":
        """Drop unknown types, unnamed entities, duplicates and dangling or self relations.
        LLM output is untrusted: only these validated values reach the database."""
        allowed_types, allowed_relations = set(entity_types), set(relation_types)
        entities: dict[str, ExtractedEntity] = {}
        for e in self.entities:
            key = entity_key(e.name)
            if key and e.type in allowed_types and key not in entities:
                entities[key] = ExtractedEntity(e.name.strip()[:200], e.type, e.description[:500])
            if len(entities) >= max_entities:
                break
        relations = {
            (entity_key(r.source), r.relation, entity_key(r.target))
            for r in self.relations
            if r.relation in allowed_relations
        }
        return Extraction(
            tuple(entities.values()),
            tuple(
                ExtractedRelation(entities[s].name, rel, entities[t].name)
                for s, rel, t in sorted(relations)
                if s in entities and t in entities and s != t
            ),
        )


# --- ingest writes (sdlc_ingest; call inside the document's transaction) -----------------------


async def cached_json(conn: AsyncConnection, cache_key: str) -> dict | None:
    """A cached model result (extraction_cache, ingest only). Keys are namespaced by their users:
    graph extraction uses a bare sha256, PDF page reading `ocr:<sha256>`."""
    cur = await conn.execute(
        "SELECT result FROM extraction_cache WHERE cache_key = %s", (cache_key,)
    )
    row = await cur.fetchone()
    return row[0] if row else None


async def store_json(conn: AsyncConnection, cache_key: str, result: dict) -> None:
    await conn.execute(
        "INSERT INTO extraction_cache (cache_key, result) VALUES (%s, %s)"
        " ON CONFLICT (cache_key) DO UPDATE SET result = EXCLUDED.result, created_at = now()",
        (cache_key, Jsonb(result)),
    )


async def cached_extraction(conn: AsyncConnection, cache_key: str) -> Extraction | None:
    data = await cached_json(conn, cache_key)
    return Extraction.from_json(data) if data is not None else None


async def store_extraction(conn: AsyncConnection, cache_key: str, extraction: Extraction) -> None:
    await store_json(conn, cache_key, extraction.to_json())


@dataclass
class GraphCounts:
    entities: int = 0
    relations: int = 0


async def write_graph(
    conn: AsyncConnection,
    source_id: str,
    classification_rank: int,
    chunk_ids: Sequence[int],
    extractions: Sequence[Extraction],
) -> GraphCounts:
    """Upsert entities (one per source+key; first type/name wins, longest description kept) and
    add mentions/edges for each chunk."""
    counts = GraphCounts()
    for chunk_id, extraction in zip(chunk_ids, extractions, strict=True):
        ids: dict[str, int] = {}
        for e in extraction.entities:
            cur = await conn.execute(
                """
                INSERT INTO entities (source_id, classification_rank, key, name, type, description)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_id, key) DO UPDATE SET description = CASE
                    WHEN length(EXCLUDED.description) > length(entities.description)
                    THEN EXCLUDED.description ELSE entities.description END
                RETURNING id
                """,
                (
                    source_id,
                    classification_rank,
                    entity_key(e.name),
                    e.name,
                    e.type,
                    e.description,
                ),
            )
            ids[entity_key(e.name)] = (await cur.fetchone())[0]
            await conn.execute(
                "INSERT INTO mentions (entity_id, chunk_id, source_id, classification_rank)"
                " VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (ids[entity_key(e.name)], chunk_id, source_id, classification_rank),
            )
            counts.entities += 1
        for r in extraction.relations:
            await conn.execute(
                """
                INSERT INTO edges
                    (source_id, classification_rank, src_id, dst_id, relation, chunk_id)
                VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
                """,
                (
                    source_id,
                    classification_rank,
                    ids[entity_key(r.source)],
                    ids[entity_key(r.target)],
                    r.relation,
                    chunk_id,
                ),
            )
            counts.relations += 1
    return counts


async def drop_orphan_entities(conn: AsyncConnection, source_id: str) -> int:
    """Entities whose chunks were all replaced or deleted."""
    cur = await conn.execute(
        """
        DELETE FROM entities e WHERE e.source_id = %s
          AND NOT EXISTS (SELECT 1 FROM mentions m WHERE m.entity_id = e.id)
        """,
        (source_id,),
    )
    return cur.rowcount


# --- retrieval (sdlc_app, inside scoped()) -------------------------------------------------------


@dataclass(frozen=True)
class GraphEntity:
    key: str
    name: str
    type: str
    source_id: str
    description: str
    depth: int


@dataclass(frozen=True)
class GraphEdge:
    source: str  # entity name
    relation: str
    target: str
    source_id: str


@dataclass
class GraphResult:
    hits: list[SearchHit] = field(default_factory=list)
    entities: list[GraphEntity] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    seeds: list[str] = field(default_factory=list)


# row layout: 0 id, 1 source_id, 2 path, 3 start_line, 4 end_line, 5 heading, 6 content,
# 7 score, 8 media_type
_CHUNK_COLUMNS = """c.id, c.source_id, d.path, c.start_line, c.end_line, c.heading, c.content,
                    1 - (c.embedding <=> %(vec)s::vector) AS score, d.media_type"""

_WALK = """
WITH RECURSIVE walk(key, depth) AS (
    SELECT k, 0 FROM unnest(%(seeds)s::text[]) AS k
  UNION
    SELECT n.key, w.depth + 1
    FROM walk w
    JOIN LATERAL (
        SELECT d.key FROM entities s
          JOIN edges e ON e.src_id = s.id JOIN entities d ON d.id = e.dst_id
         WHERE s.key = w.key
        UNION
        SELECT s.key FROM entities d
          JOIN edges e ON e.dst_id = d.id JOIN entities s ON s.id = e.src_id
         WHERE d.key = w.key
    ) n ON true
    WHERE w.depth < %(hops)s
)
SELECT key, min(depth) AS depth FROM walk GROUP BY key ORDER BY depth, key LIMIT %(max_keys)s
"""


async def graph_search(
    conn: AsyncConnection,
    policy: EffectivePolicy,
    embedding: Sequence[float],
    query: str,
    k: int = 5,
    hops: int = 1,
    boost_sources: Iterable[str] = (),
) -> GraphResult:
    k = max(1, min(int(k), 20))
    hops = max(0, min(int(hops), MAX_HOPS))
    boost = set(boost_sources)
    params = {"vec": vector_literal(embedding), "n": VECTOR_CANDIDATES}
    result = GraphResult()
    async with scoped(conn, policy):
        await conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
        await conn.execute("SET LOCAL hnsw.ef_search = 100")
        cur = await conn.execute(
            f"""SELECT {_CHUNK_COLUMNS} FROM chunks c JOIN documents d ON d.id = c.document_id
                ORDER BY c.embedding <=> %(vec)s::vector LIMIT %(n)s""",  # noqa: S608
            params,
        )
        candidates = {row[0]: (row, None) for row in await cur.fetchall()}

        # seeds: entities in the best chunks + entities named in the question
        best = [cid for cid in list(candidates)[:SEED_CHUNKS]]
        cur = await conn.execute(
            """
            SELECT DISTINCT e.key FROM mentions m JOIN entities e ON e.id = m.entity_id
             WHERE m.chunk_id = ANY(%(best)s)
            UNION
            SELECT DISTINCT key FROM entities
             WHERE length(key) >= 4 AND position('-' || key || '-' IN %(qkey)s) > 0
            """,
            {"best": best, "qkey": f"-{entity_key(query)}-"},
        )
        seeds = sorted(row[0] for row in await cur.fetchall())
        result.seeds = seeds
        if seeds:
            cur = await conn.execute(_WALK, {"seeds": seeds, "hops": hops, "max_keys": MAX_KEYS})
            depth_by_key = dict(await cur.fetchall())
            keys, depths = list(depth_by_key), list(depth_by_key.values())
            cur = await conn.execute(
                f"""
                SELECT {_CHUNK_COLUMNS}, min(w.depth) AS depth
                FROM unnest(%(keys)s::text[], %(depths)s::int[]) AS w(key, depth)
                JOIN entities e ON e.key = w.key
                JOIN mentions m ON m.entity_id = e.id
                JOIN chunks c ON c.id = m.chunk_id
                JOIN documents d ON d.id = c.document_id
                GROUP BY c.id, d.path, d.media_type
                """,  # noqa: S608
                {**params, "keys": keys, "depths": depths},
            )
            for row in await cur.fetchall():
                candidates[row[0]] = (row[:-1], row[-1])
            cur = await conn.execute(
                """
                SELECT key, name, type, source_id, description FROM entities
                 WHERE key = ANY(%(keys)s) ORDER BY key, source_id
                """,
                {"keys": keys},
            )
            result.entities = [
                GraphEntity(key, name, type_, source_id, description, depth_by_key[key])
                for key, name, type_, source_id, description in await cur.fetchall()
            ]
            cur = await conn.execute(
                """
                SELECT DISTINCT s.name, e.relation, d.name, e.source_id
                FROM edges e JOIN entities s ON s.id = e.src_id JOIN entities d ON d.id = e.dst_id
                WHERE s.key = ANY(%(keys)s) AND d.key = ANY(%(keys)s)
                ORDER BY 1, 2, 3 LIMIT %(max)s
                """,
                {"keys": keys, "max": MAX_EDGES},
            )
            result.edges = [GraphEdge(*row) for row in await cur.fetchall()]

    def ranked(item):
        row, depth = item
        bonus = GRAPH_BONUS.get(depth, 0.0) if depth is not None else 0.0
        return float(row[7]) + bonus + (GLOSSARY_BOOST if row[1] in boost else 0.0)

    top, per_doc = [], {}
    for item in sorted(candidates.values(), key=ranked, reverse=True):
        doc = (item[0][1], item[0][2])  # (source_id, path)
        if per_doc.get(doc, 0) < MAX_PER_DOCUMENT:
            per_doc[doc] = per_doc.get(doc, 0) + 1
            top.append(item)
        if len(top) == k:
            break
    result.hits = [
        SearchHit(
            *row[1:7],
            score=ranked((row, depth)),
            via="graph" if depth is not None else "vector",
            media_type=row[8],
        )
        for row, depth in top
    ]
    return result


def summarize(result: GraphResult) -> str:
    """Compact text view (debugging / logs)."""
    return json.dumps(
        {
            "seeds": result.seeds,
            "hits": [(h.source_id, h.path, round(h.score, 3), h.via) for h in result.hits],
            "edges": [(e.source, e.relation, e.target) for e in result.edges][:10],
        }
    )

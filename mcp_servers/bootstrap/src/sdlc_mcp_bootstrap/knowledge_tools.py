"""Knowledge tools: search_knowledge (Stage 5, vector) and graph_query (Stage 6, vector + knowledge
graph). Data access is enforced twice: the caller's policy selects the
sources and classification ceiling, and Postgres row-level security filters every row on them
(sdlc_db.scoped). A bug here cannot widen access beyond what RLS allows.
"""

import asyncio
from dataclasses import dataclass, field

from psycopg_pool import AsyncConnectionPool
from sdlc_db import Embedder, graph_search, search

from sdlc_mcp_bootstrap.identity import request_identity


@dataclass
class Knowledge:
    pool: AsyncConnectionPool  # sdlc_app role (read-only, RLS); created closed
    embedder: Embedder
    _opened: bool = False
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def open_pool(self) -> AsyncConnectionPool:
        """Open the pool on first use, inside the server's event loop."""
        if not self._opened:
            async with self._lock:
                if not self._opened:
                    await self.pool.open()
                    self._opened = True
        return self.pool


def make_knowledge_tools(knowledge: Knowledge) -> list:
    async def search_knowledge(query: str, k: int = 5) -> dict:
        """Search the team knowledge you may read (docs, code, runbooks). Returns the most
        relevant snippets with source, path and line range. k: number of results (max 20)."""
        ident = await request_identity()
        policy = ident.policy
        result = {
            "query": query,
            "searched_sources": list(policy.readable_sources),
            "max_classification": policy.max_classification,
            "results": [],
        }
        if not policy.readable_sources or not query.strip():
            return result
        [vector] = await asyncio.to_thread(knowledge.embedder.embed, [query], "query")
        pool = await knowledge.open_pool()
        async with pool.connection() as conn:
            hits = await search(conn, policy, vector, k)
        result["results"] = [
            {
                "source": h.source_id,
                "path": h.path,
                "lines": [h.start_line, h.end_line],
                "heading": h.heading,
                "score": round(h.score, 4),
                "snippet": h.content,
            }
            for h in hits
        ]
        return result

    async def graph_query(query: str, k: int = 5, hops: int = 1) -> dict:
        """Answer questions that span several documents (which service runs where, who owns it,
        which incident affected it, which runbook applies) using the knowledge graph plus
        semantic search, over the knowledge you may read. Returns the best document per match
        (source, path, lines, snippet, and whether it was reached via the graph), plus the
        entities and relations found. k: results (max 20). hops: graph distance, 1 or 2."""
        ident = await request_identity()
        policy = ident.policy
        result = {
            "query": query,
            "searched_sources": list(policy.readable_sources),
            "max_classification": policy.max_classification,
            "hops": max(0, min(int(hops), 2)),
            "results": [],
            "entities": [],
            "relations": [],
        }
        if not policy.readable_sources or not query.strip():
            return result
        # team context (config: teams/<team>.yaml addons.context.glossary_source) biases ranking
        glossary = {c["glossary_source"] for c in policy.context.values() if "glossary_source" in c}
        [vector] = await asyncio.to_thread(knowledge.embedder.embed, [query], "query")
        pool = await knowledge.open_pool()
        async with pool.connection() as conn:
            found = await graph_search(conn, policy, vector, query, k, hops, glossary)
        result["results"] = [
            {
                "source": h.source_id,
                "path": h.path,
                "lines": [h.start_line, h.end_line],
                "heading": h.heading,
                "score": round(h.score, 4),
                "via": h.via,
                "snippet": h.content,
            }
            for h in found.hits
        ]
        result["entities"] = [
            {
                "name": e.name,
                "type": e.type,
                "source": e.source_id,
                "hops": e.depth,
                "description": e.description,
            }
            for e in found.entities[:40]
        ]
        result["relations"] = [
            {"from": e.source, "relation": e.relation, "to": e.target, "source": e.source_id}
            for e in found.edges
        ]
        return result

    return [search_knowledge, graph_query]

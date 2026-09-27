"""Knowledge tools (Stage 5). Data access is enforced twice: the caller's policy selects the
sources and classification ceiling, and Postgres row-level security filters every row on them
(sdlc_db.scoped). A bug here cannot widen access beyond what RLS allows.
"""

import asyncio
from dataclasses import dataclass, field

from psycopg_pool import AsyncConnectionPool
from sdlc_db import Embedder, search

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
            "searched_sources": sorted(policy.data_sources),
            "max_classification": policy.max_classification,
            "results": [],
        }
        if not policy.data_sources or not query.strip():
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

    return [search_knowledge]

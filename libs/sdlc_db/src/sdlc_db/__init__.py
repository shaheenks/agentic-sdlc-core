"""Postgres/pgvector access. See libs/sdlc_db/README.md.

Every read of knowledge data goes through `scoped()`, which sets the row-level-security context
(allowed sources + classification ceiling) from the caller's EffectivePolicy. Without it, the
database returns no rows. Artifact metadata (`sdlc_db.artifacts`) goes through `owner_scoped()`.
"""

from sdlc_db.artifacts import owner_scoped
from sdlc_db.connect import conninfo
from sdlc_db.embedding import Embedder, GeminiEmbedder, HashEmbedder
from sdlc_db.graph import GraphResult, entity_key, graph_search
from sdlc_db.knowledge import SearchHit, search
from sdlc_db.scoped import rls_settings, scoped

__all__ = [
    "Embedder",
    "GeminiEmbedder",
    "GraphResult",
    "HashEmbedder",
    "SearchHit",
    "conninfo",
    "entity_key",
    "graph_search",
    "owner_scoped",
    "rls_settings",
    "scoped",
    "search",
]

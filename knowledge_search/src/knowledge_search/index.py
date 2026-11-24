"""The in-memory index over the JSONL store, and the queries (FR-KNOW-002, FR-AUTHZ-004).

Every query first narrows the store to the readable sources and only then scores: vectors are compared, and
keyword statistics (document frequencies, average length) are computed, over readable chunks alone, so neither
results nor their ranking depend on records the caller may not read."""

import math
from collections import Counter, deque
from collections.abc import Collection, Sequence
from dataclasses import dataclass

import numpy as np
from sdlc_knowledge import Chunk, Entity, Store, tokens

VECTOR, KEYWORD, HYBRID = "vector", "keyword", "hybrid"
MODES = (VECTOR, KEYWORD, HYBRID)
K1, B = 1.2, 0.75
RRF_K = 60
POOL = 50  # candidates from each side of a hybrid query


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


class Index:
    def __init__(self, store: Store) -> None:
        self.manifest = store.manifest
        self.chunks = store.chunks
        self.by_source: dict[str, np.ndarray] = {}
        for i, c in enumerate(self.chunks):
            self.by_source.setdefault(c.source_id, []).append(i)  # type: ignore[arg-type]
        self.by_source = {s: np.array(ix, dtype=np.int64) for s, ix in self.by_source.items()}
        dims = len(self.chunks[0].embedding) if self.chunks else 0
        self.vectors = np.array([c.embedding for c in self.chunks], dtype=np.float32).reshape(len(self.chunks), dims)
        self.terms = [Counter(tokens(f"{c.path} {c.heading} {c.text}")) for c in self.chunks]
        self.lengths = np.array([sum(t.values()) for t in self.terms], dtype=np.float32)
        self.postings: dict[str, set[int]] = {}
        for i, t in enumerate(self.terms):
            for term in t:
                self.postings.setdefault(term, set()).add(i)
        self.entities: dict[str, Entity] = {e.id: e for e in store.entities}
        self.adjacent: dict[str, list[tuple[str, str, str, str]]] = {}  # id -> (from, to, kind, source)
        for e in store.edges:
            for node in (e.from_id, e.to_id):
                self.adjacent.setdefault(node, []).append((e.from_id, e.to_id, e.kind, e.source_id))

    @property
    def embedding_model(self) -> str:
        return (self.manifest.get("embedding") or {}).get("model", "")

    def readable(self, sources: Collection[str]) -> np.ndarray:
        parts = [self.by_source[s] for s in sorted(set(sources)) if s in self.by_source]
        return np.sort(np.concatenate(parts)) if parts else np.array([], dtype=np.int64)

    def _vector(self, rows: np.ndarray, query: Sequence[float], limit: int) -> list[tuple[int, float]]:
        if not len(rows):
            return []
        scores = self.vectors[rows] @ np.asarray(query, dtype=np.float32)
        top = np.argsort(-scores)[:limit]
        return [(int(rows[i]), float(scores[i])) for i in top]

    def _keyword(self, rows: np.ndarray, query: str, limit: int) -> list[tuple[int, float]]:
        terms = list(dict.fromkeys(tokens(query)))
        if not len(rows) or not terms:
            return []
        allowed = set(rows.tolist())
        n, avg = len(rows), float(self.lengths[rows].mean()) or 1.0
        scores: dict[int, float] = {}
        for term in terms:
            docs = self.postings.get(term, set()) & allowed
            if not docs:
                continue
            idf = math.log(1 + (n - len(docs) + 0.5) / (len(docs) + 0.5))
            for i in docs:
                tf = self.terms[i][term]
                length = float(self.lengths[i])
                scores[i] = scores.get(i, 0.0) + idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * length / avg))
        return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]

    def search(
        self, mode: str, sources: Collection[str], limit: int, query: str, vector: Sequence[float] | None
    ) -> list[Hit]:
        rows = self.readable(sources)
        if mode == VECTOR:
            ranked = self._vector(rows, vector or (), limit)
        elif mode == KEYWORD:
            ranked = self._keyword(rows, query, limit)
        else:
            fused: dict[int, float] = {}
            for side in (self._vector(rows, vector or (), POOL), self._keyword(rows, query, POOL)):
                for rank, (i, _) in enumerate(side):
                    fused[i] = fused.get(i, 0.0) + 1.0 / (RRF_K + rank + 1)
            ranked = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
        return [Hit(self.chunks[i], score) for i, score in ranked]

    def graph(
        self, sources: Collection[str], *, entity: str = "", name: str = "", depth: int = 1, limit: int = 100
    ) -> dict:
        """The neighbourhood of an entity (by ID) or of the entities whose name matches, within the readable
        sources: no node or edge of another source is visited or returned."""
        readable = set(sources)

        def visible(node: str) -> bool:
            e = self.entities.get(node)
            return e is not None and e.source_id in readable

        if entity:
            seeds = [entity] if visible(entity) else []
        else:
            needle = name.strip().lower()
            matches = [
                e
                for e in self.entities.values()
                if e.source_id in readable and needle and (needle in e.name.lower() or needle in e.description.lower())
            ]
            # exact names first, then exact titles, then names containing the text, then descriptions
            matches.sort(
                key=lambda e: (
                    e.name.lower() != needle,
                    e.description.lower() != needle,
                    needle not in e.name.lower(),
                    len(e.name),
                    e.id,
                )
            )
            seeds = [e.id for e in matches[:5]]
        seen, edges = set(seeds), set()
        queue = deque((s, 0) for s in seeds)
        while queue and len(seen) < limit:
            node, d = queue.popleft()
            if d >= depth:
                continue
            for a, b, kind, source in self.adjacent.get(node, ()):
                if source not in readable or not (visible(a) and visible(b)):
                    continue
                edges.add((a, b, kind))
                other = b if a == node else a
                if other not in seen and len(seen) < limit:
                    seen.add(other)
                    queue.append((other, d + 1))
        nodes = [self.entities[n] for n in sorted(seen)]
        return {
            "seeds": seeds,
            "nodes": [
                {k: getattr(e, k) for k in ("id", "kind", "name", "path", "description", "source_id")} for e in nodes
            ],
            "edges": [{"from": a, "to": b, "kind": k} for a, b, k in sorted(edges) if a in seen and b in seen],
        }

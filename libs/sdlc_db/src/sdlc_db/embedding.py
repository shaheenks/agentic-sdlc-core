"""Text embeddings for the knowledge index (one model for the whole index, platform.yaml).

GeminiEmbedder: Vertex AI / Gemini API via google-genai (credentials from env / ADC).
HashEmbedder:   deterministic, offline vectors for TESTS ONLY (similar texts share tokens).
"""

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol

Kind = str  # "document" | "query"


class Embedder(Protocol):
    model: str
    dimensions: int

    def embed(self, texts: Sequence[str], kind: Kind = "document") -> list[list[float]]: ...


# Models that accept only ONE content per embedContent call. gemini-embedding-2 (multimodal)
# silently merges a list of texts into a single embedding, so it must be called per text.
SINGLE_INPUT_MODELS = frozenset({"gemini-embedding-2"})


class GeminiEmbedder:
    """Task type RETRIEVAL_DOCUMENT for chunks, RETRIEVAL_QUERY for queries. Batches where the
    model supports it; otherwise one request per text, `concurrency` at a time. The number of
    vectors is always checked against the number of texts."""

    batch_size = 50

    def __init__(self, model: str, dimensions: int, client=None, concurrency: int = 8):
        from google import genai  # imported lazily so tests need no credentials

        self.model, self.dimensions = model, dimensions
        self._client = client or genai.Client()
        self._types = genai.types
        self._concurrency = concurrency
        self._single = model in SINGLE_INPUT_MODELS

    def _call(self, contents, task: str) -> list[list[float]]:
        result = self._client.models.embed_content(
            model=self.model,
            contents=contents,
            config=self._types.EmbedContentConfig(
                task_type=task, output_dimensionality=self.dimensions
            ),
        )
        return [list(e.values) for e in result.embeddings]

    def embed(self, texts: Sequence[str], kind: Kind = "document") -> list[list[float]]:
        task = "RETRIEVAL_QUERY" if kind == "query" else "RETRIEVAL_DOCUMENT"
        texts = list(texts)
        vectors: list[list[float]] = []
        if self._single:
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=self._concurrency) as pool:
                for result in pool.map(lambda t: self._call(t, task), texts):
                    vectors.extend(result)
        else:
            for start in range(0, len(texts), self.batch_size):
                vectors.extend(self._call(texts[start : start + self.batch_size], task))
        if len(vectors) != len(texts) or any(len(v) != self.dimensions for v in vectors):
            raise RuntimeError(
                f"{self.model}: got {len(vectors)} embeddings for {len(texts)} texts "
                f"(expected {self.dimensions} dims each)"
            )
        return [_normalize(v) for v in vectors]


class HashEmbedder:
    """Bag-of-words hashing into a unit vector. Not semantic; for tests and offline dev only."""

    def __init__(self, model: str = "hash-test", dimensions: int = 768):
        self.model, self.dimensions = model, dimensions

    def embed(self, texts: Sequence[str], kind: Kind = "document") -> list[list[float]]:
        vectors = []
        for text in texts:
            vec = [0.0] * self.dimensions
            for token in re.findall(r"[a-z0-9]+", text.lower()):
                digest = hashlib.sha256(token.encode()).digest()
                vec[int.from_bytes(digest[:4], "big") % self.dimensions] += 1.0
            vectors.append(_normalize(vec))
        return vectors


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]

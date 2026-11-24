"""Embedders shared by ingest (documents) and search (queries), so both sides use the same model (DEC-0011)."""

import asyncio
import hashlib
import math
import os
import re
from collections.abc import Mapping, Sequence
from typing import Protocol

DOCUMENT, QUERY = "RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"
DEFAULT_MODEL = "gemini-embedding-001"
DEFAULT_DIMENSIONS = 768
DEFAULT_LOCATION = "europe-west3"
HASH_MODEL = "hash-v1"
MAX_CHARS = 8000  # well inside the model's input limit; chunks are much smaller
WORD = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*")


def tokens(text: str) -> list[str]:
    """Lower-case words; `snake_case` names also yield their parts."""
    out: list[str] = []
    for word in WORD.findall(text.lower()):
        out.append(word)
        if "_" in word:
            out.extend(p for p in word.split("_") if p)
    return out


def normalise(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class Embedder(Protocol):
    model: str
    dimensions: int

    async def embed(self, texts: Sequence[str], task: str) -> list[list[float]]: ...


class HashEmbedder:
    """Deterministic bag-of-words vectors: no cloud access, for local runs and tests. Similar words, not
    similar meanings."""

    model = HASH_MODEL

    def __init__(self, dimensions: int = DEFAULT_DIMENSIONS) -> None:
        self.dimensions = dimensions

    def _one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokens(text):
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0 if digest[4] & 1 else -1.0
        return normalise(vector)

    async def embed(self, texts: Sequence[str], task: str) -> list[list[float]]:
        return [self._one(t) for t in texts]


class VertexEmbedder:
    """`gemini-embedding-001` (or another model) on Vertex AI, one text per request, a few at a time, retried
    with backoff when throttled. Vectors are normalised: below full size the model's are not."""

    def __init__(
        self,
        project: str,
        location: str = DEFAULT_LOCATION,
        model: str = DEFAULT_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
        concurrency: int = 8,
        client=None,
    ) -> None:
        if client is None:
            from google import genai

            client = genai.Client(vertexai=True, project=project, location=location)
        self.client = client
        self.model = model
        self.dimensions = dimensions
        self._slots = asyncio.Semaphore(concurrency)

    async def _one(self, text: str, task: str) -> list[float]:
        from google.genai import errors, types

        config = types.EmbedContentConfig(task_type=task, output_dimensionality=self.dimensions)
        delay = 1.0
        for attempt in range(6):
            try:
                async with self._slots:
                    response = await self.client.aio.models.embed_content(
                        model=self.model, contents=text[:MAX_CHARS] or " ", config=config
                    )
                return normalise(response.embeddings[0].values)
            except errors.APIError as exc:
                if exc.code not in (429, 500, 503) or attempt == 5:
                    raise
                await asyncio.sleep(delay)
                delay *= 2
        raise AssertionError("unreachable")

    async def embed(self, texts: Sequence[str], task: str) -> list[list[float]]:
        return list(await asyncio.gather(*(self._one(t, task) for t in texts)))


def embedder_from_env(environ: Mapping[str, str] | None = None) -> Embedder:
    e = os.environ if environ is None else environ
    kind = e.get("EMBEDDINGS", "vertex")
    dimensions = int(e.get("EMBEDDING_DIMENSIONS", str(DEFAULT_DIMENSIONS)))
    if kind == "hash":
        return HashEmbedder(dimensions)
    if kind != "vertex":
        raise SystemExit(f"EMBEDDINGS must be vertex or hash, not {kind!r}")
    project = e.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise SystemExit("GOOGLE_CLOUD_PROJECT must be set for EMBEDDINGS=vertex")
    return VertexEmbedder(
        project,
        e.get("VERTEX_LOCATION", DEFAULT_LOCATION),
        e.get("EMBEDDING_MODEL", DEFAULT_MODEL),
        dimensions,
    )

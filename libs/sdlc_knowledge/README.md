# sdlc_knowledge

The [Knowledge Store](../../spec/components/knowledge-store.md)'s first format (DEC-0011), shared by
`knowledge_ingest` (the only writer) and `knowledge_search` (the only reader):

- `chunks.jsonl`, `entities.jsonl`, `edges.jsonl`: one record per line, each with `source_id` and
  `classification`; reading refuses a record without them.
- `manifest.json`: the ingest run, the embedding model and dimensions, and the status of each source.
- Embedders: `VertexEmbedder` (`gemini-embedding-001` on Vertex AI, 768 dimensions, normalised) and
  `HashEmbedder` (deterministic, no cloud access) for local runs and tests. `embedder_from_env()` picks one
  from `EMBEDDINGS` (`vertex` or `hash`), `GOOGLE_CLOUD_PROJECT`, `VERTEX_LOCATION` (default `europe-west3`),
  `EMBEDDING_MODEL` and `EMBEDDING_DIMENSIONS`.

Test from this folder: `uv run pytest`.

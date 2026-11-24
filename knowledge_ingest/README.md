# knowledge_ingest

Ingests declared sources into JSONL files; runs in the build pipeline.

**Phase 0 skeleton.** Cloud Run job; locally `uv run sdlc-knowledge-ingest`.

Build and test from this folder: `uv run pytest`.

| Variable | Default | Meaning |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Minimum log level |

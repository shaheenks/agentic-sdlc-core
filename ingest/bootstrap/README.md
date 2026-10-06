# ingest/bootstrap

`sdlc-ingest`: builds the knowledge store from `config/sources/*.yaml` (Stage 5; graph extraction in Stage 6).

```
sdlc-ingest run --source <id> [--source <id> ...] | --all  [--dry-run] [--force]
```

Per source: sync the `sources` registry (classification, owner) → walk the source (`local_folder`: the folder;
`git`: the commit `spec.ref`, read with `git ls-tree`/`cat-file`, so uncommitted changes are never indexed) with include/exclude
globs (binary files skipped) → skip files whose content hash is unchanged (`--force` re-embeds them) →
chunk (`spec.ingest.chunking`: `markdown` by headings, `code` by top-level definitions, `fixed` windows,
`auto` by extension; tiny sections merge forward) → embed (`platform.yaml` `knowledge.embedding`) →
replace the document's chunks in one transaction → delete documents whose files are gone.
Classification is stamped on every row from the Source config; changing it re-stamps existing rows.

**PDFs** (`pdf.py`, H10): detected by the `%PDF-` header. Each page's text layer is read with pypdf; pages with
almost no text (scans) are sent to `platform.yaml` `knowledge.ocr.model` one page at a time, only for sources
with `spec.ingest.pdf.ocr: gemini`, and cached (`ocr:` keys in `extraction_cache`). `chunk_pdf` builds sections
from the bookmarks (heading = bookmark path; a section starts at its title line) or per page, and stores **page**
ranges in the chunks (`documents.media_type = application/pdf`). Over `max_mb`/`max_pages`, encrypted or corrupt
PDFs are reported and not written. Files without any text are recorded with no chunks (not re-read every run;
`--force` re-reads them, e.g. after turning OCR on). The run summary adds `pdf_pages`, `ocr_calls` and
`pages_without_text`.

**Graph extraction** (`extract.py`, sources with `spec.ingest.graph.enabled`): every changed chunk of a source goes
to `platform.yaml` `knowledge.graph.model` in one parallel batch (structured JSON, the Source's entity/relation
types). Output is cleaned before it is stored, and cached in `sdlc.extraction_cache` (key: prompt version, model,
types, text), so `--force` re-runs are cheap. A file whose extraction fails is not written and is retried next
run. The run summary shows `entities`, `relations` and `llm_calls` (cache misses); the exit code is 1 on errors.

Runs as `sdlc_ingest` (writes only through its RLS policy; no superuser, no BYPASSRLS).
`--dry-run` walks and chunks without touching the DB or the embedding API.

- Host: `uv run --env-file .env sdlc-ingest run --all`
- Docker (on demand, profile `ingest`): `docker compose run --rm ingest run --all`

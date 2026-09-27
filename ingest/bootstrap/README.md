# ingest/bootstrap

`sdlc-ingest`: builds the knowledge store from `config/sources/*.yaml` (Stage 5; graph extraction in Stage 6).

```
sdlc-ingest run --source <id> [--source <id> ...] | --all  [--dry-run] [--force]
```

Per source: sync the `sources` registry (classification, owner) → walk `spec.location` with include/exclude
globs (binary files skipped) → skip files whose content hash is unchanged (`--force` re-embeds them) →
chunk (`spec.ingest.chunking`: `markdown` by headings, `code` by top-level definitions, `fixed` windows,
`auto` by extension; tiny sections merge forward) → embed (`platform.yaml` `knowledge.embedding`) →
replace the document's chunks in one transaction → delete documents whose files are gone.
Classification is stamped on every row from the Source config; changing it re-stamps existing rows.

Runs as `sdlc_ingest` (writes only through its RLS policy; no superuser, no BYPASSRLS).
`--dry-run` walks and chunks without touching the DB or the embedding API.

- Host: `uv run --env-file .env sdlc-ingest run --all`
- Docker (on demand, profile `ingest`): `docker compose run --rm ingest run --all`

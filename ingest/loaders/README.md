# ingest/loaders (`sdlc_loaders`)

Source loaders for the ingest pipeline (version-01 M0). A loader reads one source and yields `SourceItem`s;
`ingest/bootstrap` (`sdlc_ingest`) chunks, embeds and writes them. Loaders never touch the database.

| Module | What |
|---|---|
| `base.py` | `SourceItem` (path = stable item id, text or PDF bytes, `content_hash`, `media_type`, `title`, `url`, `updated_at`, `restricted`) and the `Loader` contract: `items(cursor)`, `all_ids()` (incremental loaders), `cursor`, `details` |
| `files.py` | Include/exclude globs, text/PDF detection, the folder walker and the git reader (pinned ref, partial clone of https URLs) |
| `local.py` | `local_folder` loader (full scans) |
| `git.py` | `git` loader (M1): local or https (GitHub, Bitbucket Cloud/DC); pinned SHA or tracked branch read at FETCH_HEAD; incremental via `git diff` from the stored commit; per-provider auth header (host-scoped `http.<url>.extraHeader` in git's environment) and deep links |
| `registry.py` | `LOADERS` (source type -> factory) and `make_loader(source, repo_root, cache_root, secrets)` |
| `http.py` | `HttpClient` for remote loaders: host allowlist on every request and redirect, 429/5xx backoff with `Retry-After`, timeouts, credentials as a per-request header callable, one re-read of the secret after a 401 |

Adding a source type: a factory in `LOADERS`, its `spec` block in `config/schemas/source.schema.json`, its type in
`sdlc_config.loader.CREDENTIAL_SOURCE_TYPES` if it reads `spec.credentials`, and tests against recorded HTTP
fixtures (`httpx.MockTransport`). Credentials come from `sdlc_secrets` (`{env: ...}` / `{secret: ...}`), never from
config values, and are never logged.

Tests: `tests/ingest/` (`test_loaders.py`, `test_http.py`, plus the walker tests).

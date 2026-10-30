# ingest/loaders (`sdlc_loaders`)

Source loaders for the ingest pipeline (version-01 M0). A loader reads one source and yields `SourceItem`s;
`ingest/bootstrap` (`sdlc_ingest`) chunks, embeds and writes them. Loaders never touch the database.

| Module | What |
|---|---|
| `base.py` | `SourceItem` (path = stable item id, text or PDF bytes, `content_hash`, `media_type`, `title`, `url`, `updated_at`, `restricted`) and the `Loader` contract: `items(cursor)`, `all_ids()` (incremental loaders), `cursor`, `details` |
| `files.py` | Include/exclude globs, text/PDF detection, the folder walker and the git reader (pinned ref, partial clone of https URLs) |
| `local.py` | `local_folder` loader (full scans) |
| `git.py` | `git` loader (M1): local or https (GitHub, Bitbucket Cloud/DC); pinned SHA or tracked branch read at FETCH_HEAD; incremental via `git diff` from the stored commit; per-provider auth header (host-scoped `http.<url>.extraHeader` in git's environment) and deep links |
| `gcs.py` | `gcs` loader (M2): GCS JSON API with ADC (read-only scope), paged listing under the prefix, downloads only objects whose generation changed (cursor), size limits from the listing, links to the object |
| `atlassian.py` | Shared by Confluence/Jira: secret `<email>:<token>` -> Basic (Cloud), `<token>` -> Bearer (DC PAT); client factory |
| `confluence.py` | `confluence` loader (M3): REST v1 CQL search (Cloud and DC), every run lists pages with versions, ancestors and read restrictions; restricted pages/descendants skipped and deleted (fail closed when restrictions are not returned); bodies only for changed versions; PDF attachments of allowed pages |
| `jira.py` | `jira` loader (M4): Cloud REST v3 `search/jql` (nextPageToken) or DC REST v2 `search` (startAt); every run lists keys with `updated` + `security`; issues with a security level skipped and deleted; full fields only for changed issues, rendered as one Markdown document per issue (no people fields) |
| `registry.py` | `LOADERS` (source type -> factory) and `make_loader(source, repo_root, cache_root, secrets)` |

Shared with the MCP server and therefore in `libs/sdlc_connectors` (version-01 M6): `HttpClient` (host allowlist, retries,
credentials never to cross-host redirects) and the Confluence/Jira Markdown converters. `LoaderError` is
`sdlc_connectors.ConnectorError`, so HTTP failures are loader errors.

Adding a source type: a factory in `LOADERS` (`factory(source, LoaderContext)`), its `spec` keys in
`config/schemas/source.schema.json` and `sdlc_config.loader.TYPE_OPTIONS`, its type in
`sdlc_config.loader.CREDENTIAL_SOURCE_TYPES` if it reads `spec.credentials`, and tests against recorded HTTP
fixtures (`httpx.MockTransport`). Credentials come from `sdlc_secrets` (`{env: ...}` / `{secret: ...}`), never from
config values, and are never logged.

Tests: `tests/ingest/` (`test_loaders.py`, `test_http.py`, plus the walker tests).

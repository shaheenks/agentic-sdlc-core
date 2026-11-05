# sdlc_artifacts

Content store and limits for documents the agent saves for a user (version-03 P5). Used only by the
MCP server (`sdlc_core_mcp.artifact_tools`); metadata and ownership are in Postgres
(`sdlc.artifacts`, `sdlc_db.artifacts`, owner-only RLS).

- **Keys:** `artifacts/<owner oid>/<artifact id>`, built by `object_key()` from the verified token's
  oid and a new uuid, never from user input.
- **Backends** (`SDLC_ARTIFACT_STORE`): `file:///data/artifacts` (compose volume `mcp-artifacts`,
  core-mcp only), `gs://<bucket>[/<prefix>]` (GCP; the MCP service account needs `objectUser` on the
  bucket), empty = artifacts off. GCS uploads use `ifGenerationMatch=0` (never overwrite).
- **Limits** (`limits.py`): text only (`text/markdown`, `text/plain`, `text/csv`,
  `application/json`) with a matching extension, 1 MiB, plain file names (no paths), 50 live
  artifacts per user.
- **Retention:** `SDLC_ARTIFACT_RETENTION_DAYS` (default 7) sets `expires_at`; keep it equal to the
  bucket lifecycle (`artifact_retention_days` in Terraform). Expired rows are deleted on the owner's
  next save or list, their content best effort (the bucket lifecycle removes the rest).

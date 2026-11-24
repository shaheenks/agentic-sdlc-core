# code_workspace

Cloud Run job where ci_workflow_agent edits code and runs a repository's build and tests.

**Phase 0 skeleton.** Cloud Run job; locally `uv run sdlc-code-workspace`.

Build and test from this folder: `uv run pytest`.

| Variable | Default | Meaning |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Minimum log level |

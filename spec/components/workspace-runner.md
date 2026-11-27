---
type: Component
title: Workspace Runner
description: The shared code both MCP servers use to start the Code Workspace - request folders in the artifact bucket, the Cloud Run job execution and its result - for the system job and the credential-free user job.
tags: [component, capability, execution]
status: draft
x-layer: capability
x-folder: libs/sdlc_workspace/
x-depends-on: [/components/code-workspace, /components/artifact-store]
x-satisfies: [/requirements/functional/FR-SDLC-006, /requirements/non-functional/NFR-ARCH-003]
---

# Purpose

Both MCP servers start the [Code Workspace](code-workspace.md): [event_agent_mcp](event-agent-mcp.md) the system
job for unattended runs ([DEC-0015](../decisions/DEC-0015.md)), and [user_agent_mcp](user-agent-mcp.md) the
credential-free user job for a change the user implements in chat ([DEC-0016](../decisions/DEC-0016.md)). How a
request reaches the job and its result comes back is the same for both, so it lives once, in `libs/sdlc_workspace`.

# Responsibilities

- A new folder per execution under `<prefix>/<run-id>/workspace-<n>/` of the artifact bucket: `artifacts/system/runs`
  for the system job, `artifacts/users/<user-id>/runs` for the user job. No other prefix is accepted.
- Write `request.json` and its input files (the repository archive of a user's run), start the job with
  `REQUEST_PATH` as its only override, wait for the execution, and read `result.json`.
- Remove input files once the job has run; the request and the result stay until the bucket's lifecycle deletes them.
- In the local environment, run the Code Workspace in process, in user mode without any system token.

# Out of scope

- What the job does with a request: the [Code Workspace](code-workspace.md).
- Which change is built, for whom, and whether it may be: the MCP servers.

# Interfaces

- Provides: `execute(runner, store_root, prefix, run_id, request, files)`, `executions(...)`, `JobRunner(job,
  timeout)`, `LocalRunner(mode)`, `WorkspaceFailed`.
- Consumes: the Cloud Run Admin API (`jobs.run` with overrides, then the operation) with the server's own account.

# Depends on

- [Code Workspace](code-workspace.md)
- [Artifact Store](artifact-store.md)

# Owns

- Nothing; the requests and results are in the artifact bucket.

# Requirements

- [FR-SDLC-006: Implementation plan and implementation with the user](../requirements/functional/FR-SDLC-006.md)
- [NFR-ARCH-003: Self-contained components](../requirements/non-functional/NFR-ARCH-003.md)

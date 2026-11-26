# event_agent_mcp

The MCP server for scheduled and event-triggered runs, as the system identity
([DEC-0007](../../spec/decisions/DEC-0007.md), [DEC-0015](../../spec/decisions/DEC-0015.md),
[component](../../spec/components/event-agent-mcp.md)). Cloud Run service with internal ingress; MCP revision
2026-07-28 over streamable HTTP, stateless.

Every request to `/mcp` comes from the event agents' runtime:
- `Authorization: Bearer <Google ID token>` of a service account declared under `identity.callers` for a surface
  marked `system: true` (`event_agents`), for this server's `PUBLIC_URL`; whatever `identity.mode` is. Only in the
  local environment, in mode `trusted_header`, may it send `X-SDLC-Surface: event_agents` instead. A request that
  forwards a user (`X-SDLC-User-*`) is refused, and user_agent_mcp refuses this caller.
- The run: `X-SDLC-Team` (one of `system.yaml`'s teams), `X-SDLC-Subscription` (a declared, enabled subscription)
  and `X-SDLC-Run-Id`; the event: `X-SDLC-Event-Source`, `-Type`, `-Delivery`, `-Subject`.

The server lists and allows the tools of the system identity's tool groups (`system_policy`), and a write tool only
when the run's subscription lists it under `writes`. Every list, call and refusal is audited with the event's
metadata, never argument values.

| Tools | What they do |
|---|---|
| `feature_status`, `control_read_file` | The feature's artifacts and approvals on its branch, each target's plan, Jira keys, writes |
| `repo_list`, `repo_read_file`, `repo_pull_requests` | The team's product repositories |
| `plan_open_pull_request` | `plan-<repo>.md` from `sdlc/<id>/plan-<repo>` into `feature/<id>` on the control repository; needs the design merged by a person |
| `workspace_run` | A change set built and tested in the Code Workspace and pushed to `sdlc/<id>/<repo>`; needs the plan merged by a person |
| `implementation_open_pull_request` | From `sdlc/<id>/<repo>` into `feature/<id>` on the target repository, with the Jira keys |
| `pull_request_comment` | On one of the feature's pull requests, to say what blocks the run |

No tool merges, approves or pushes to `main` or `feature/*`; each write is recorded in the feature's `links.yaml`.

Build and test from this folder: `uv run pytest`.

| Variable | Default | Meaning |
|---|---|---|
| `PORT` | `8081` | Port to listen on (Cloud Run sets it) |
| `SDLC_ENV` | `local` | Environment name |
| `CONFIG_SOURCE` | - | Configuration bucket (`gs://...`) or folder; required |
| `STORE_MOUNT_PATH` | - | Mount point of the artifact bucket; Code Workspace requests go under `artifacts/system/runs/`; required |
| `PUBLIC_URL` | `http://localhost:8081` | This server's URL, the audience of callers' ID tokens |
| `SYSTEM_TOKEN_<PROVIDER>` | - | The machine user's token for a provider, for example `SYSTEM_TOKEN_GITHUB` (Secret Manager) |
| `WORKSPACE_MODE` | - | `job` (the Cloud Run job in `WORKSPACE_JOB`), `local` (in process, local environment only) or empty (none) |
| `WORKSPACE_JOB` | - | `projects/<p>/locations/<r>/jobs/<name>` |
| `WORKSPACE_TIMEOUT_SECONDS` | `1200` | One Code Workspace execution's limit |
| `CONFIG_REFRESH_SECONDS` | `30` | How often the active bundle is re-checked |
| `LOG_LEVEL` | `INFO` | Minimum log level |

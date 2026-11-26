---
type: Component
title: "user_agent_mcp"
description: "The MCP server for agents acting for a user: sdlc_ui and agents on Agent Runtime call it for a verified user, and every action is scoped to that user's ID."
tags: [component, capability, security]
status: draft
x-layer: capability
x-folder: mcp_servers/user_agent_mcp/
x-depends-on: [/components/identity, /components/access-policy, /components/configuration-registry, /components/artifact-store, /components/connectors, /components/secrets, /components/knowledge-search, /components/workflow-catalog, /components/workflow-engine, /components/human-tasks, /components/audit-log, /components/observability]
x-satisfies: [/requirements/functional/FR-SURF-004, /requirements/functional/FR-SURF-006, /requirements/functional/FR-IDN-001, /requirements/functional/FR-IDN-002, /requirements/functional/FR-AUTHZ-002, /requirements/functional/FR-AUTHZ-003, /requirements/functional/FR-AUTHZ-005, /requirements/functional/FR-AUTHZ-006, /requirements/functional/FR-CFG-005, /requirements/functional/FR-WFL-003, /requirements/functional/FR-HUM-005, /requirements/functional/FR-AGT-001, /requirements/functional/FR-AGT-003, /requirements/functional/FR-CONN-001, /requirements/functional/FR-CONN-005, /requirements/functional/FR-KNOW-002, /requirements/functional/FR-ART-001, /requirements/functional/FR-ART-002, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-ARCH-002, /requirements/non-functional/NFR-ARCH-003, /requirements/non-functional/NFR-ARCH-004, /requirements/non-functional/NFR-SEC-001, /requirements/non-functional/NFR-SEC-004, /requirements/non-functional/NFR-PRIV-001, /requirements/non-functional/NFR-AUD-001, /requirements/non-functional/NFR-OBS-001, /requirements/non-functional/NFR-REL-001, /requirements/non-functional/NFR-PERF-001, /requirements/non-functional/NFR-OPS-001, /requirements/non-functional/NFR-OPS-002, /requirements/functional/FR-AUTHZ-008, /requirements/functional/FR-WFL-009, /requirements/non-functional/NFR-ARCH-006, /requirements/functional/FR-AGT-005, /requirements/functional/FR-SDLC-005, /requirements/functional/FR-KNOW-004, /requirements/functional/FR-MDL-002, /requirements/functional/FR-SDLC-013]
---

# Purpose

The MCP server for user calls ([DEC-0002](../decisions/DEC-0002.md), accepted; [DEC-0005](../decisions/DEC-0005.md), accepted). Agents on Agent Runtime use it to act for the signed-in user, and the action touches only that user's own resources ([FR-AUTHZ-008](../requirements/functional/FR-AUTHZ-008.md)). Scheduled and event-triggered runs use [event_agent_mcp](event-agent-mcp.md) instead ([DEC-0007](../decisions/DEC-0007.md)). Coding harnesses (Google Antigravity, Gemini CLI, Claude Code) can connect to it directly with the user's Google account token once that surface is enabled ([FR-SURF-006](../requirements/functional/FR-SURF-006.md), parked). It is one of exactly two MCP servers ([NFR-ARCH-006](../requirements/non-functional/NFR-ARCH-006.md)).

# Responsibilities

- Establish the user of every request through [Identity](identity.md): for now forwarded by sdlc_ui or the
  agent runtime, each proven by its service account's ID token, which names the calling surface
  ([DEC-0010](../decisions/DEC-0010.md)); later the user's own Google account token
  ([DEC-0009](../decisions/DEC-0009.md)). Refuse requests without a verified user, and refuse the system identity.
- Resolve the effective policy from the active bundle in the configuration bucket, read while answering and
  cached by object generation ([Configuration Registry](configuration-registry.md)).
- List and allow only the tools in the surface's tool groups that the user may use, as the
  [Access Policy](access-policy.md) decides, including argument constraints and rate limits.
- Artifact tools: save, read, list and delete the user's own artifacts under `artifacts/users/<user ID>/` of the
  mounted [Artifact Store](artifact-store.md) bucket ([DEC-0006](../decisions/DEC-0006.md)). Paths are built from the verified user ID only.
- Connection tools: list connections and their status; start a new or replacement connection for GitHub,
  Bitbucket, Jira, Confluence and other declared providers; test and revoke a connection. Secrets are entered
  on a secure page outside the conversation, encrypted with a key from Secret Manager and written to
  `secrets/users/<user ID>/` ([Secrets](secrets.md));
  no tool accepts or returns one.
- Domain tools: reads and writes in downstream systems through [Connectors](connectors.md) with the user's own
  connection; a tool classed as a write runs only after its required approval.
- Knowledge tools: proxy search and graph queries to [Knowledge Search](knowledge-search.md) with a filter
  attribute built from the user's data scope; the user's token is not forwarded.
- Workflow tools for coding harnesses (parked): list and describe workflows, start and cancel runs, get a run, list and
  answer the user's tasks.
- Identity tool: show the caller's identity and effective access.
- Serve the same operations as an HTTP API for sdlc_ui (Connections page, artifacts).
- Audit every list and call with user ID, surface, tool, decision, run and configuration version; never argument values.

# Out of scope

- Running knowledge queries: [Knowledge Search](knowledge-search.md).
- Running workflows: the [Workflow Engine](workflow-engine.md).

# Interfaces

- Provides: a remote MCP server over streamable HTTP, with OAuth protected-resource metadata naming Google as the
  authorization server; an HTTP API with the same operations for sdlc_ui; the secure secret-entry page.
- Consumes: token verification, the configuration bucket, the artifact bucket mount (`STORE_MOUNT_PATH`), connectors, the
  knowledge search service, the workflow catalog, the run API and human tasks; service URLs from environment variables.

# Depends on

- [Identity](identity.md)
- [Access Policy](access-policy.md)
- [Configuration Registry](configuration-registry.md)
- [Artifact Store](artifact-store.md)
- [Connectors](connectors.md)
- [Secrets](secrets.md)
- [Knowledge Search](knowledge-search.md)
- [Workflow Catalog](workflow-catalog.md)
- [Workflow Engine](workflow-engine.md)
- [Human Tasks](human-tasks.md)
- [Audit Log](audit-log.md)
- [Observability](observability.md)

# Owns

- The tool registry and tool-group definitions it serves; no user data of its own.

# Requirements

- [FR-SURF-004: Same behaviour on every surface](../requirements/functional/FR-SURF-004.md)
- [FR-SURF-006: Direct MCP access from coding harnesses](../requirements/functional/FR-SURF-006.md)
- [FR-IDN-001: Sign-in with Cloud Identity, federated from Entra ID](../requirements/functional/FR-IDN-001.md)
- [FR-IDN-002: Act as the user end to end](../requirements/functional/FR-IDN-002.md)
- [FR-AUTHZ-002: Selective disclosure](../requirements/functional/FR-AUTHZ-002.md)
- [FR-AUTHZ-003: Authorize every call](../requirements/functional/FR-AUTHZ-003.md)
- [FR-AUTHZ-005: Rate limits and quotas](../requirements/functional/FR-AUTHZ-005.md)
- [FR-AUTHZ-006: Tool groups per surface](../requirements/functional/FR-AUTHZ-006.md)
- [FR-CFG-005: Configuration bucket](../requirements/functional/FR-CFG-005.md)
- [FR-WFL-003: Start a run](../requirements/functional/FR-WFL-003.md)
- [FR-HUM-005: Approval before writes](../requirements/functional/FR-HUM-005.md)
- [FR-AGT-001: Bounded agent steps](../requirements/functional/FR-AGT-001.md)
- [FR-AGT-003: User agent MCP server](../requirements/functional/FR-AGT-003.md)
- [FR-CONN-001: Per-user connections](../requirements/functional/FR-CONN-001.md)
- [FR-CONN-005: Secrets never pass through agents](../requirements/functional/FR-CONN-005.md)
- [FR-KNOW-002: Knowledge search](../requirements/functional/FR-KNOW-002.md)
- [FR-ART-001: Artifacts with lineage](../requirements/functional/FR-ART-001.md)
- [FR-ART-002: Artifact ownership](../requirements/functional/FR-ART-002.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-ARCH-002: Hostnames and service URLs are configuration](../requirements/non-functional/NFR-ARCH-002.md)
- [NFR-ARCH-003: Self-contained components](../requirements/non-functional/NFR-ARCH-003.md)
- [NFR-ARCH-004: Knowledge backend isolated](../requirements/non-functional/NFR-ARCH-004.md)
- [NFR-SEC-001: Authorization only in the platform's services](../requirements/non-functional/NFR-SEC-001.md)
- [NFR-SEC-004: Where secrets live](../requirements/non-functional/NFR-SEC-004.md)
- [NFR-PRIV-001: No sensitive content in telemetry](../requirements/non-functional/NFR-PRIV-001.md)
- [NFR-AUD-001: Audit every decision](../requirements/non-functional/NFR-AUD-001.md)
- [NFR-OBS-001: End-to-end trace per run](../requirements/non-functional/NFR-OBS-001.md)
- [NFR-REL-001: 99.5% availability](../requirements/non-functional/NFR-REL-001.md)
- [NFR-PERF-001: Application response under 5 seconds on average](../requirements/non-functional/NFR-PERF-001.md)
- [NFR-OPS-001: Reproducible images](../requirements/non-functional/NFR-OPS-001.md)
- [NFR-OPS-002: Local Docker Compose environment](../requirements/non-functional/NFR-OPS-002.md)
- [FR-AUTHZ-008: Per-user isolation of sessions, artifacts and secrets](../requirements/functional/FR-AUTHZ-008.md)
- [FR-WFL-009: Resume after signing in again](../requirements/functional/FR-WFL-009.md)
- [NFR-ARCH-006: Two MCP servers, one per class of caller](../requirements/non-functional/NFR-ARCH-006.md)
- [FR-AGT-005: Ad-hoc knowledge search and brainstorm chat](../requirements/functional/FR-AGT-005.md)
- [FR-SDLC-005: Design specification hand-off](../requirements/functional/FR-SDLC-005.md)
- [FR-KNOW-004: Knowledge scope: broad in chat, team in workflows](../requirements/functional/FR-KNOW-004.md)
- [FR-MDL-002: Usage limits](../requirements/functional/FR-MDL-002.md)
- [FR-SDLC-013: Team control repository](../requirements/functional/FR-SDLC-013.md)

# Realisation

- Folder `mcp_servers/user_agent_mcp/`, self-contained; shares identity, policy, directory and configuration
  code with event_agent_mcp through libraries under `libs/`.
- One Cloud Run service `user-agent-mcp` in europe-west3 (Cloud Run service names allow no underscores). The
  artifact bucket's `artifacts/users/` and `secrets/users/` are mounted as two Cloud Storage volumes
  (`only-dir`), since Cloud Storage FUSE writes a folder object for each directory it creates; IAM conditions
  limit its service account to those prefixes, as objects and as folders. The invoker role only for sdlc_ui's
  and the agent runtime's service accounts ([DEC-0010](../decisions/DEC-0010.md)); ingress `all` in development
  until sdlc_ui runs there, internal from then on. Cloud Run reserves paths ending in `z`, so `/healthz` answers
  only the platform's own probes.
- MCP specification revision 2026-07-28, the current stable one, through the official Python SDK; its stateless
  core (no protocol sessions) lets any Cloud Run instance serve any request.
- Built in phase 1: the identity tool (`whoami`), the artifact tools, and the connection tools without a
  connection test (it comes with the connectors). Saving a secret is an HTTP API operation only, in its own tool
  group, which only sdlc_ui's surface is given. The HTTP API maps each route to its tool, so the same policy, rate
  limits and audit apply. Calls may carry `X-SDLC-Run-Id` and `X-SDLC-Step` for the audit record and lineage;
  each audit record names the user, the surface and the caller that vouched for the user.
- Runs in the local Docker Compose environment against local or development-project dependencies.

# Open questions

- Parked with the coding-harness surface: is URL-mode elicitation supported by the harnesses we need?
- Knowledge tools ([DEC-0011](../decisions/DEC-0011.md)): `knowledge_search` and `knowledge_graph`
  proxy to [Knowledge Search](knowledge-search.md) (`KNOWLEDGE_SEARCH_URL`) with the readable sources of the
  caller's effective policy as the filter attribute, and this service's own ID token from the metadata server.
  A run's team comes from the declared caller's `X-SDLC-Team` header; a team the user is not in is refused
  (403, audited) and a team run reads only its team's sources. Knowledge Search accepts internal traffic only,
  so the service sends all egress through the platform VPC (Private Google Access; no Cloud NAT yet) ([FR-KNOW-004](../requirements/functional/FR-KNOW-004.md)).
- Jira and repository tools (phase 4a): `team_systems`, `jira_get_issue`, `jira_search`, `jira_create_feature`,
  `jira_link_design`, `repo_list`, `repo_read_file` and `connection_test`,
  with the user's own connection. Argument constraints ([FR-AUTHZ-003](../requirements/functional/FR-AUTHZ-003.md)):
  the Jira projects and repositories come from the team's systems in configuration, never from arguments; reads
  reach the user's teams' systems (in a team run, that team's), writes need a team run; the server builds the JQL,
  and a team's lists of Jira projects and repositories each have a default.
- The team's control repository ([DEC-0012](../decisions/DEC-0012.md), [FR-SDLC-013](../requirements/functional/FR-SDLC-013.md)):
  `control_publish` opens a pull request with `features/<control-id>/feature.md` or `design.md` (front matter
  written by the server: control ID, team, author, the previous artifact) on a branch `sdlc/<control-id>/<kind>-…`;
  `control_status` reports each artifact's approval (on the main branch, last changed by a pull request merged by
  someone who is not a declared system account), the writes recorded in `links.yaml`, and on request the text; it
  finds a feature by control ID or by the `sdlc-control <id>` link on its Jira feature. `jira_create_feature` and
  `jira_link_design` refuse (`not_approved`) unless the artifact is approved, refuse a second creation
  (`already_done`), and record their results (or the error) in `links.yaml` with the artifact commit and who
  approved it. All need a team run.
- Connections are checked when saved: `connection_save` signs in to the provider with the token first and refuses
  one the provider rejects (`invalid_token`, nothing stored); a token that cannot be checked here (no team site,
  the server unreachable, Confluence) is stored as untested. A Jira Cloud token needs the account email.
  `POST /api/connections/{provider}/test` runs `connection_test`, which signs in with the stored token and says
  as whom ([FR-CONN-001](../requirements/functional/FR-CONN-001.md)).
- Feature branches ([DEC-0013](../decisions/DEC-0013.md)): `feature_open` opens `feature/<control-id>` on the control
  repository with `feature.md` and the chat approval (who, when) written by the server, reusing an open feature of
  the same ID or name; `feature_target_branches` opens it on the target repositories; approvals, `links.yaml` and the
  design pull request use the feature branch (main for features published before DEC-0013).
  `jira_create_feature` creates the Epic (when confirmed), the Feature under it and the stories as its sub-tasks,
  reusing open issues of the same summary; `jira_search` can restrict to open issues.

---
type: Component
title: "event_agent_mcp"
description: "The standalone MCP server for scheduled and event-triggered runs: agents call it as the system identity, and it reaches only system connections and system artifacts."
tags: [component, capability, security]
status: draft
x-layer: capability
x-folder: mcp_servers/event_agent_mcp/
x-depends-on: [/components/identity, /components/access-policy, /components/configuration-registry, /components/artifact-store, /components/connectors, /components/control-repository, /components/secrets, /components/knowledge-search, /components/audit-log, /components/observability, /components/code-workspace]
x-satisfies: [/requirements/functional/FR-AGT-004, /requirements/functional/FR-IDN-004, /requirements/functional/FR-CONN-004, /requirements/functional/FR-AUTHZ-003, /requirements/functional/FR-AUTHZ-005, /requirements/functional/FR-CFG-005, /requirements/functional/FR-HUM-005, /requirements/functional/FR-KNOW-002, /requirements/functional/FR-ART-001, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-ARCH-002, /requirements/non-functional/NFR-ARCH-003, /requirements/non-functional/NFR-ARCH-004, /requirements/non-functional/NFR-SEC-001, /requirements/non-functional/NFR-SEC-004, /requirements/non-functional/NFR-SEC-006, /requirements/non-functional/NFR-PRIV-001, /requirements/non-functional/NFR-AUD-001, /requirements/non-functional/NFR-OBS-001, /requirements/non-functional/NFR-REL-001, /requirements/non-functional/NFR-OPS-001, /requirements/non-functional/NFR-OPS-002, /requirements/functional/FR-TRIG-003, /requirements/non-functional/NFR-OBS-003, /requirements/non-functional/NFR-OPS-003, /requirements/non-functional/NFR-ARCH-006, /requirements/functional/FR-SDLC-006, /requirements/functional/FR-SDLC-007, /requirements/functional/FR-SDLC-008, /requirements/functional/FR-SDLC-009, /requirements/functional/FR-SDLC-010, /requirements/functional/FR-SDLC-011, /requirements/functional/FR-SDLC-012, /requirements/functional/FR-MDL-002]
---

# Purpose

The tool server for unattended runs ([DEC-0007](../decisions/DEC-0007.md), accepted). Agents of a scheduled or event-triggered run act as the
system identity here, with only the tools and system connections declared for it, and never reach a user's resources. It is one of exactly two MCP servers ([NFR-ARCH-006](../requirements/non-functional/NFR-ARCH-006.md)) and is never reachable from coding harnesses.

# Responsibilities

- Verify on every request, through [Identity](identity.md), a token of the event agents' Agent Runtime
  service account (the system identity); refuse any other token, including a user's.
- Accept traffic only from that deployment: internal ingress and Cloud Run invoker for that service account only.
- Resolve the system identity's effective policy from the active bundle in the configuration bucket
  ([Configuration Registry](configuration-registry.md)) and list and allow only its declared tool groups, through
  the [Access Policy](access-policy.md).
- Domain tools: reads and writes in downstream systems through [Connectors](connectors.md) with system connections
  only; a write runs only after its required approval.
- Read system connection PATs from environment variables (Secret Manager references; no expiry or rotation) and save
  run artifacts under `artifacts/system/` of the mounted artifact bucket ([Secrets](secrets.md),
  [Artifact Store](artifact-store.md), [DEC-0006](../decisions/DEC-0006.md)).
- Knowledge tools: proxy to [Knowledge Search](knowledge-search.md) with a filter attribute built from the system
  identity's data scope.
- Write each run's results back to the downstream systems the workflow declares, through write tools
  ([FR-TRIG-003](../requirements/functional/FR-TRIG-003.md)).
- Continue the run's trace and audit every list and call with the system identity, the event metadata, tool,
  decision and configuration version; never argument values ([NFR-OBS-003](../requirements/non-functional/NFR-OBS-003.md)).

# Out of scope

- Anything owned by a user: [user_agent_mcp](user-agent-mcp.md).
- Receiving events and starting runs: the [Event Gateway](event-gateway.md).

# Interfaces

- Provides: a remote MCP server over streamable HTTP for agents of unattended runs.
- Consumes: token verification, the configuration bucket, the artifact bucket mount (`STORE_MOUNT_PATH`), connectors,
  the knowledge search service; service URLs from environment variables.

# Depends on

- [Identity](identity.md)
- [Access Policy](access-policy.md)
- [Configuration Registry](configuration-registry.md)
- [Artifact Store](artifact-store.md)
- [Connectors](connectors.md)
- [Control Repository](control-repository.md)
- [Secrets](secrets.md)
- [Knowledge Search](knowledge-search.md)
- [Audit Log](audit-log.md)
- [Observability](observability.md)
- [Code Workspace](code-workspace.md)

# Owns

- Nothing durable; system artifacts are stored in the artifact bucket.

# Requirements

- [FR-AGT-004: Event agent MCP server](../requirements/functional/FR-AGT-004.md)
- [FR-IDN-004: System identity for unattended runs](../requirements/functional/FR-IDN-004.md)
- [FR-CONN-004: System connections](../requirements/functional/FR-CONN-004.md)
- [FR-AUTHZ-003: Authorize every call](../requirements/functional/FR-AUTHZ-003.md)
- [FR-AUTHZ-005: Rate limits and quotas](../requirements/functional/FR-AUTHZ-005.md)
- [FR-CFG-005: Configuration bucket](../requirements/functional/FR-CFG-005.md)
- [FR-HUM-005: Approval before writes](../requirements/functional/FR-HUM-005.md)
- [FR-KNOW-002: Knowledge search](../requirements/functional/FR-KNOW-002.md)
- [FR-ART-001: Artifacts with lineage](../requirements/functional/FR-ART-001.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-ARCH-002: Hostnames and service URLs are configuration](../requirements/non-functional/NFR-ARCH-002.md)
- [NFR-ARCH-003: Self-contained components](../requirements/non-functional/NFR-ARCH-003.md)
- [NFR-ARCH-004: Knowledge backend isolated](../requirements/non-functional/NFR-ARCH-004.md)
- [NFR-SEC-001: Authorization only in the platform's services](../requirements/non-functional/NFR-SEC-001.md)
- [NFR-SEC-004: Where secrets live](../requirements/non-functional/NFR-SEC-004.md)
- [NFR-SEC-006: Least-privilege service identities](../requirements/non-functional/NFR-SEC-006.md)
- [NFR-PRIV-001: No sensitive content in telemetry](../requirements/non-functional/NFR-PRIV-001.md)
- [NFR-AUD-001: Audit every decision](../requirements/non-functional/NFR-AUD-001.md)
- [NFR-OBS-001: End-to-end trace per run](../requirements/non-functional/NFR-OBS-001.md)
- [NFR-REL-001: 99.5% availability](../requirements/non-functional/NFR-REL-001.md)
- [NFR-OPS-001: Reproducible images](../requirements/non-functional/NFR-OPS-001.md)
- [NFR-OPS-002: Local Docker Compose environment](../requirements/non-functional/NFR-OPS-002.md)
- [FR-TRIG-003: Results of unattended runs go back to the systems involved](../requirements/functional/FR-TRIG-003.md)
- [NFR-OBS-003: Event metadata on every trace of an unattended run](../requirements/non-functional/NFR-OBS-003.md)
- [NFR-OPS-003: Revoke and replace a leaked system connection PAT](../requirements/non-functional/NFR-OPS-003.md)
- [NFR-ARCH-006: Two MCP servers, one per class of caller](../requirements/non-functional/NFR-ARCH-006.md)
- [FR-SDLC-006: Implementation by ci_workflow_agent](../requirements/functional/FR-SDLC-006.md)
- [FR-SDLC-007: Security vulnerability analysis of pull requests](../requirements/functional/FR-SDLC-007.md)
- [FR-SDLC-008: Deployment handling](../requirements/functional/FR-SDLC-008.md)
- [FR-SDLC-009: Alert triage and log analysis](../requirements/functional/FR-SDLC-009.md)
- [FR-SDLC-010: Incident and bug reporting](../requirements/functional/FR-SDLC-010.md)
- [FR-SDLC-011: Quality assurance analysis of pull requests](../requirements/functional/FR-SDLC-011.md)
- [FR-SDLC-012: Jira tasks from findings](../requirements/functional/FR-SDLC-012.md)
- [FR-MDL-002: Usage limits](../requirements/functional/FR-MDL-002.md)

# Realisation

- Folder `mcp_servers/event_agent_mcp/`, self-contained; shares token verification, policy, audit and connector
  code with user_agent_mcp through libraries under `libs/` ([DEC-0005](../decisions/DEC-0005.md), accepted).
- MCP specification revision 2026-07-28, the current stable one.
- One Cloud Run service `event-agent-mcp` in europe-west3 under its own service account, with the artifact bucket
  mounted as a Cloud Storage volume; IAM conditions limit it to `artifacts/system/`; system connection secrets as environment variables.

# Open questions

- The network path from Agent Runtime to an internal-ingress Cloud Run service (Private Service Connect interface or network attachment) is set up with the infrastructure.
- Built ([DEC-0015](../decisions/DEC-0015.md), phase 5a milestone 2): the system identity is a declared caller of a
  surface marked `system: true`, proved by its Google ID token and forwarding no user; each request names its run
  (team, subscription, run ID) and event (source, type, delivery, subject). Tools: `feature_status`,
  `control_read_file`, `repo_list`, `repo_read_file`, `repo_pull_requests`, and the writes `plan_open_pull_request`,
  `workspace_run`, `implementation_open_pull_request` and `pull_request_comment`, each allowed only when the run's
  subscription lists it. Approvals come from the [Control Repository](control-repository.md) library; the machine
  user's token per provider is `SYSTEM_TOKEN_<PROVIDER>`; the Code Workspace is started as a Cloud Run job with the
  request under `artifacts/system/runs/<run-id>/`. Knowledge search for unattended runs comes later.

---
type: Component
title: "Artifact Store"
description: "A dedicated Cloud Storage bucket, mounted by the MCP servers, for the files runs produce (deleted 7 days after creation) and, for now, connection secrets; everything in it belongs to one user or to the system identity."
tags: [component, records, data]
status: draft
x-layer: records
x-depends-on: [/components/access-policy, /components/audit-log]
x-satisfies: [/requirements/functional/FR-SURF-001, /requirements/functional/FR-AGT-003, /requirements/functional/FR-ART-001, /requirements/functional/FR-ART-002, /requirements/functional/FR-ART-003, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-HOST-005, /requirements/non-functional/NFR-REL-002, /requirements/non-functional/NFR-PERF-001, /requirements/functional/FR-AUTHZ-008, /requirements/non-functional/NFR-SEC-004, /requirements/functional/FR-SDLC-002, /requirements/functional/FR-SDLC-003, /requirements/functional/FR-SDLC-005]
---

# Purpose

The output of a workflow (a design review, a test plan, generated stories) lives here for 7 days, linked to the run and node that produced it and visible only to its owner. For now the bucket also holds connection secrets under a separate prefix ([DEC-0006](../decisions/DEC-0006.md)).

# Responsibilities

- Store artifacts with type, owner (a user, or the system identity), producing run and node, and classification
  as object metadata, under `artifacts/users/<user ID>/` or `artifacts/system/`.
- Keep earlier versions readable while a revision is saved within the 7 days.
- Delete every artifact 7 days after creation through a lifecycle rule on the `artifacts/` prefix; `secrets/` is
  not affected.
- Allow reading by the owner only ([FR-AUTHZ-008](../requirements/functional/FR-AUTHZ-008.md)); no team or
  explicit sharing for now.
- Enforce size and type limits.
- Audit creation, denied reads and deletion.

# Out of scope

- Publishing to downstream systems, which is a write tool through [Connectors](connectors.md).
- Access by users directly: they reach artifacts through [user_agent_mcp](user-agent-mcp.md).

# Interfaces

- Provides: the bucket as a Cloud Storage volume mount for user_agent_mcp and event_agent_mcp, each limited by IAM conditions to its prefixes; short-lived download links.
- Consumes: access decisions.

# Depends on

- [Access Policy](access-policy.md)
- [Audit Log](audit-log.md)

# Owns

- Artifact content, metadata and versions, for 7 days.

# Requirements

- [FR-SURF-001: Custom UI](../requirements/functional/FR-SURF-001.md)
- [FR-AGT-003: User agent MCP server](../requirements/functional/FR-AGT-003.md)
- [FR-ART-001: Artifacts with lineage](../requirements/functional/FR-ART-001.md)
- [FR-ART-002: Artifact ownership](../requirements/functional/FR-ART-002.md)
- [FR-ART-003: Artifact retention of 7 days](../requirements/functional/FR-ART-003.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-HOST-005: Single region europe-west3](../requirements/non-functional/NFR-HOST-005.md)
- [NFR-REL-002: Multi-zone production](../requirements/non-functional/NFR-REL-002.md)
- [NFR-PERF-001: Application response under 5 seconds on average](../requirements/non-functional/NFR-PERF-001.md)
- [FR-AUTHZ-008: Per-user isolation of sessions, artifacts and secrets](../requirements/functional/FR-AUTHZ-008.md)
- [NFR-SEC-004: Where secrets live](../requirements/non-functional/NFR-SEC-004.md)
- [FR-SDLC-002: Features and user stories](../requirements/functional/FR-SDLC-002.md)
- [FR-SDLC-003: Design specification](../requirements/functional/FR-SDLC-003.md)
- [FR-SDLC-005: Design specification hand-off](../requirements/functional/FR-SDLC-005.md)

# Realisation

- One Cloud Storage bucket per environment in europe-west3: uniform bucket-level access, lifecycle rule deleting
  objects under `artifacts/` 7 days after creation, IAM conditions on object-name prefixes per service account.
  No database ([DEC-0003](../decisions/DEC-0003.md)). Prefix layout: [DEC-0006](../decisions/DEC-0006.md).
- Each version of an artifact is two objects, `<name>/<NNNN>.json` (metadata and lineage) and
  `<name>/<NNNN>.content`, so each version expires on its own and earlier versions stay readable meanwhile.
  Size and content-type limits come from `platform.yaml`.

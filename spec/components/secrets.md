---
type: Component
title: Secrets
description: "Keeps users' connection secrets encrypted under the artifact bucket's secrets/users/ prefix, and every other secret in GCP Secret Manager delivered as environment variables; never returned to agents or logs."
tags: [component, platform, security]
status: draft
x-layer: platform
x-depends-on: [/components/audit-log, /components/artifact-store]
x-satisfies: [/requirements/functional/FR-CONN-001, /requirements/functional/FR-CONN-004, /requirements/functional/FR-CONN-005, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-SEC-004, /requirements/non-functional/NFR-OPS-002, /requirements/functional/FR-AUTHZ-008, /requirements/non-functional/NFR-OPS-003]
---

# Purpose

Keeps every credential out of code, images and configuration, and every user's connection secrets visible to that user's requests only.

# Responsibilities

- Store each user's connection secrets (PATs and their metadata) under that user's prefix, encrypted by
  user_agent_mcp with a data-encryption key from Secret Manager.
- Keep system connection secrets, webhook signing secrets, OAuth client secrets and the data-encryption key in
  Secret Manager, and deliver them to services as environment variables.
- Make a user's secrets reachable only through user_agent_mcp for that user, and system connection secrets only
  in event_agent_mcp ([FR-AUTHZ-008](../requirements/functional/FR-AUTHZ-008.md)).
- Support replacement and revocation; a user can delete their own connection secrets. No key rotation for now.
- Hold system connection PATs for event_agent_mcp, which uses them to act on Jira, Confluence, Bitbucket and
  GitHub; they are not expired or rotated, and are replaced only by the manual revoke-and-replace procedure
  ([NFR-OPS-003](../requirements/non-functional/NFR-OPS-003.md)).
- Audit access by reference, never by value.

# Out of scope

- Deciding which connector a user may use: the [Access Policy](access-policy.md).

# Interfaces

- Provides: encrypted secret objects under `secrets/users/` of the mounted artifact bucket for user_agent_mcp; Secret Manager secrets as Cloud Run environment-variable references for the event gateway, event_agent_mcp, sdlc_ui and the encryption key.

# Depends on

- [Audit Log](audit-log.md)
- [Artifact Store](artifact-store.md)

# Owns

- Secret values and their metadata.

# Requirements

- [FR-CONN-001: Per-user connections](../requirements/functional/FR-CONN-001.md)
- [FR-CONN-004: System connections](../requirements/functional/FR-CONN-004.md)
- [FR-CONN-005: Secrets never pass through agents](../requirements/functional/FR-CONN-005.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-SEC-004: Where secrets live](../requirements/non-functional/NFR-SEC-004.md)
- [NFR-OPS-002: Local Docker Compose environment](../requirements/non-functional/NFR-OPS-002.md)
- [FR-AUTHZ-008: Per-user isolation of sessions, artifacts and secrets](../requirements/functional/FR-AUTHZ-008.md)
- [NFR-OPS-003: Revoke and replace a leaked system connection PAT](../requirements/non-functional/NFR-OPS-003.md)

# Realisation

- For now ([DEC-0006](../decisions/DEC-0006.md)): one object per user and provider at
  `secrets/users/<user ID>/<provider>` in the [Artifact Store](artifact-store.md) bucket, outside its lifecycle
  rule, AES-256-GCM encrypted by user_agent_mcp with the user ID and provider as associated data. To be reviewed later.
- Everything else: GCP Secret Manager regional secrets in europe-west3, mounted as environment variables.

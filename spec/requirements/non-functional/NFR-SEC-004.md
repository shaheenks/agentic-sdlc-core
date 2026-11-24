---
type: Non-Functional Requirement
title: "Where secrets live"
description: "Users' connection secrets live, encrypted by the application, under a secrets/ prefix of the artifact bucket; every other secret lives in GCP Secret Manager and reaches services as environment variables."
tags: [requirement, security]
status: draft
x-area: SEC
x-priority: must
x-implementation: planned
---

# Statement

The system shall keep users' personal access tokens and other user connection secrets, encrypted by the application, under the `secrets/users/` prefix of the artifact bucket, reached through a mount point; keep every other secret in GCP Secret Manager; and never keep a secret in the repository, images or configuration.

# Acceptance criteria

- A user's connection secrets are at `secrets/users/<user ID>/`, one object per provider, outside the 7-day
  lifecycle rule. Only user_agent_mcp mounts that prefix; no agent, model or other component can read it.
- Before writing, user_agent_mcp encrypts each secret object with AES-256-GCM under a data-encryption key it reads from GCP Secret Manager, with the user ID and provider as associated data; the object records the key version, and the key is never written to the bucket or a log.
- An object copied to another user's path, or edited, fails decryption and is treated as no connection.
- The data-encryption key is not rotated for now; each object still records the key version, so rotation can
  be added later without rewriting the format.
- System connection PATs are GCP Secret Manager secrets given to event_agent_mcp as environment variables; they are long-lived (no expiry and no rotation; a leaked one is revoked and replaced by hand, [NFR-OPS-003](NFR-OPS-003.md)) and event_agent_mcp uses them to act on Jira, Confluence, Bitbucket, GitHub and the other declared systems. The event agents themselves authenticate with their Agent Runtime
  service account and need no secret.
- Standard Cloud Logging is used for now; Data Access audit logs on the bucket are not turned on.
- System connection secrets ([FR-CONN-004](../functional/FR-CONN-004.md)), webhook signing secrets and OAuth
  client secrets are regional Secret Manager secrets in europe-west3, given to the services that need them as
  environment variables (Cloud Run secret references), readable only by those services' service accounts.
- The event gateway receives all of its secrets as environment variables.
- Configuration refers to secrets by name only, and a repository secret scan finds no credentials.
- Locally, the mount point is a git-ignored folder (`local` profile) or the development bucket through Cloud
  Storage FUSE (`gcp-dev` profile); environment-variable secrets and the encryption key come from the
  development project's Secret Manager with gcloud credentials.

# Notes

Keeping user connection secrets in the bucket is a choice for now, to be reviewed later ([DEC-0006](../../decisions/DEC-0006.md)).

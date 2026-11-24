---
type: Non-Functional Requirement
title: "Revoke and replace a leaked system connection PAT"
description: "A manual, documented procedure revokes a system connection PAT that has leaked, or may have, and puts a new one in service on event_agent_mcp."
tags: [requirement, ops, security, secrets]
status: draft
x-area: OPS
x-priority: must
x-implementation: planned
---

# Statement

The system shall provide a manual revoke-and-replace procedure for the system connection PATs of event_agent_mcp, used when a PAT has leaked or may have, or when the person who created it leaves.

# Acceptance criteria

- The procedure is a runbook in `mcp_servers/event_agent_mcp/README.md` with these steps, in order:
  1. Revoke the PAT at the provider (Jira, Confluence, Bitbucket, GitHub) at once; this alone stops its use.
  2. Create a replacement PAT with the narrowest scope the provider allows for the declared resources ([FR-CONN-004](../functional/FR-CONN-004.md)), owned by the platform's service account at the provider, not a person.
  3. Add it as a new version of the same Secret Manager secret, then disable the old version.
  4. Deploy a new event_agent_mcp revision that references the new secret version, so every instance reads it (Cloud Run resolves environment-variable secrets when an instance starts).
  5. Check that the provider's connection test passes and that no request since the revoke used the old PAT, from the provider's audit log and the platform's audit records.
  6. Record the incident: which PAT, when it was revoked, when the new one went live.
- Environment-variable secret references are pinned to a secret version, never `latest`, so step 4 is explicit.
- Between steps 1 and 4, runs that need that connection fail visibly and are retried as their steps declare; no run falls back to a user's connection.
- Every step can be done by an operator with the documented roles, without changing code or configuration.
- The procedure is rehearsed once in the development environment before production.

# Notes

System connection PATs are not expired or rotated ([NFR-SEC-004](NFR-SEC-004.md)), so this procedure is the only way one is replaced.

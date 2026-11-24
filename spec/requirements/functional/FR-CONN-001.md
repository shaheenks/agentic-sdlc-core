---
type: Functional Requirement
title: "Per-user connections"
description: "Users link their own accounts on downstream systems."
tags: [requirement, connections]
status: draft
x-area: CONN
x-priority: must
x-implementation: planned
---

# Statement

The system shall let each user link and revoke their own connection to each downstream system the platform supports.

# Acceptance criteria

- A connection uses OAuth where the provider supports it, otherwise a personal access token (PAT).
- The secret is entered only as [FR-CONN-005](FR-CONN-005.md) describes.
- The credential is stored encrypted under the user's own `secrets/users/` prefix of the artifact bucket ([NFR-SEC-004](../non-functional/NFR-SEC-004.md)) and never returned to the browser or an agent.
- First-release providers include GitHub, Bitbucket, Jira and Confluence.
- Revoking a connection stops its use at once.
- The platform supports GitHub, Bitbucket, Jira and Confluence, each in its cloud and Data Center editions; the first phase delivers Jira, GitHub and Bitbucket, and Confluence follows.

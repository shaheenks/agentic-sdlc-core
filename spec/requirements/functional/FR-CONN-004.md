---
type: Functional Requirement
title: "System connections"
description: "Unattended runs reach downstream systems through platform-owned connections scoped by configuration."
tags: [requirement, connections]
status: draft
x-area: CONN
x-priority: should
x-implementation: planned
---

# Statement

The system shall give the system identity its own connection to each downstream system that unattended runs use, scoped to the repositories, projects or spaces declared in configuration.

# Acceptance criteria

- System connection credentials are PATs (or an app installation key where a provider offers one): system connection PATs are GCP Secret Manager secrets given to event_agent_mcp as environment variables; they are long-lived (no expiry and no rotation) and event_agent_mcp uses them to act on Jira, Confluence, Bitbucket, GitHub and the other declared systems.
  They are used only there ([FR-AGT-004](FR-AGT-004.md)).
- Each system connection has the narrowest scope the provider allows for the declared resources.
- Unattended runs never use a user's connection, and user-initiated runs never use a system connection.
- Each provider's system connection belongs to a machine user distinct from every person; its login is declared
  in the environment configuration, and a merge made by it never counts as an approval ([DEC-0015](../../decisions/DEC-0015.md)).

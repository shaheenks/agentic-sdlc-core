---
type: Non-Functional Requirement
title: Agents hold no external-system credentials
description: Autonomous agents never hold credentials for external systems; server-side components use them after the policy check.
area: Security
tags:
- requirement
- non-functional
- security
status: draft
priority: must
implementation: planned
sources:
- id: design
  resource: ../../../docs/designs/workflow-platform.md
  title: Workflow platform target design
- id: change
  resource: ../../changes/CH-0008.md
  title: CH-0008 Workflow platform design baseline
---

# Statement

An agent that reads untrusted content shall not hold credentials for external systems. Every write to an external system shall go through a server-side component that holds the credential and applies the policy first.

# Acceptance criteria

- Workflow runtimes and sandboxes have no Jira, Confluence, Bitbucket, GitHub or chat credential, in their environment or in their files.
- An agent changes an external system only by emitting a typed, size-capped outcome for the delivery service, or by calling an MCP tool its workflow role grants.
- Delivery posts only the fields the workflow's channel schema allows, to the target the Trigger names.
- The MCP backend and the delivery service use a credential only after the workflow principal's authorization check, and audit each use with the credential kind.

# Notes

The credentials themselves are FR-CONN-004: broad-scoped service tokens in the initial phases. User-confirmed write tools (FR-WRITE-001) act as the user, with the user's confirmation; this requirement covers autonomous workflows.

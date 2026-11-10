---
type: Functional Requirement
title: Tools act as the user
description: Tools that reach external systems use the caller's own connection, after the policy check.
area: Connections
tags:
- requirement
- functional
- connections
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:28:01+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
---

# Statement

The system shall call external systems with the caller's own connection, only after authorization passes.

# Acceptance criteria

- Without a usable connection the tool answers 'not connected'; there is no service-credential fallback.
- A tool that uses a connection declares it in the tool catalog and its host is in the allowed hosts.
- The `tool_call` audit record carries the credential kind, connection and connection outcome.

# Notes

GitHub and Bitbucket Cloud are live. Atlassian (Jira, Confluence) and Data Center editions are built and not yet checked live (inventory gap 6).

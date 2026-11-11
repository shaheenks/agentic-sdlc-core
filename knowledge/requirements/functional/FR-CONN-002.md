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
verified:
- by: human:shaheenks
  at: '2026-11-11T16:02:28+05:30'
priority: must
implementation: live
sources:
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
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

This requirement covers the GitHub and Bitbucket Cloud connections, which are live. Atlassian (Jira, Confluence) and Data Center connections are [FR-CONN-003](FR-CONN-003.md) (modified by CH-0001).

---
type: Functional Requirement
title: Atlassian and Data Center connections
description: Users connect Atlassian Cloud and Data Center accounts, and connected tools use them as the user.
area: Connections
tags:
- requirement
- functional
- connections
status: draft
priority: should
implementation: planned
sources:
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: v03
  resource: ../../../docs/plans/version-03.md
  title: Implementation plan version-03 (P8)
- id: change
  resource: ../../changes/CH-0001.md
  title: CH-0001 Separate built capabilities from live ones
---

# Statement

The system shall let users connect their Atlassian Cloud account and their Bitbucket, Jira and Confluence Data Center accounts, and call those systems as the user.

# Acceptance criteria

- `jira_get_issue` and `confluence_get_page` use the caller's `atlassian` connection, with the same checks as [FR-CONN-002](FR-CONN-002.md).
- A Data Center connection reports who the user is on that instance before it is saved.
- Each provider has been used once against a real site, recorded in the plan (version-03 P8).

# Notes

Split out of [FR-CONN-002](FR-CONN-002.md) by [CH-0001](../../changes/CH-0001.md). The code is built and tested against fake APIs only (inventory gap 6). `implementation` is `planned` while this concept is a draft and becomes `built` when CH-0001 is done; it becomes `live` after the P8 live check.

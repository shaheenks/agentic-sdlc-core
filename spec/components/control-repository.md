---
type: Component
title: Control Repository
description: The shared rules of a team's sdlc-control repository - feature branches, where each artifact lives, who approved it, and the record of every write made from it - used by both MCP servers.
tags: [component, capability, audit]
status: draft
x-layer: capability
x-folder: libs/sdlc_control/
x-depends-on: [/components/connectors]
x-satisfies: [/requirements/functional/FR-SDLC-001, /requirements/functional/FR-SDLC-013, /requirements/functional/FR-CONN-004, /requirements/non-functional/NFR-ARCH-003]
---

# Purpose

Both MCP servers act on a team's control repository: [user_agent_mcp](user-agent-mcp.md) as the user (features,
designs) and [event_agent_mcp](event-agent-mcp.md) as the system identity (plans, implementation records). The rules
of that repository are the same for both, so they live once, in `libs/sdlc_control`
([DEC-0012](../decisions/DEC-0012.md), [DEC-0013](../decisions/DEC-0013.md), [DEC-0015](../decisions/DEC-0015.md)).

# Responsibilities

- The layout: `features/<control-id>/feature.md`, `design.md`, `plan-<repo>.md` and `links.yaml` on the feature's
  branch `feature/<control-id>`; features published before DEC-0013 on the main branch.
- Approval: a feature by the user in chat (its front matter), every other artifact by a pull request into the feature
  branch merged by a person; a merge by one of the repository's system accounts (machine users) never approves.
- The record: each write and its results appended to `links.yaml`, committed on the feature branch.
- Pull request branches: `sdlc/<control-id>/design-<hex>` and `sdlc/<control-id>/plan-<repo>`, and reading the
  feature and artifact from an open pull request's branch.
- Plans and implementations, the same for both servers ([DEC-0016](../decisions/DEC-0016.md)): a plan pull request
  only for a design a person merged and never a second one; an implementation pull request from
  `sdlc/<control-id>/<repo>` only for a plan a person merged; the change set's limits; Jira keys in the titles; each
  recorded in `links.yaml`.

# Out of scope

- Which repository is a team's and whose connection reaches it: the MCP servers, from configuration.
- The tools agents call: the MCP servers.

# Interfaces

- Provides: `ControlRepository(client, branch, system_accounts, by)` with `home`, `approval`, `read`, `links`,
  `record` and `open_pull_requests`; `open_plan`, `open_implementation`, `check_changes` and `ControlError`; the
  layout and branch helpers.
- Consumes: a repository connector from [Connectors](connectors.md).

# Depends on

- [Connectors](connectors.md)

# Owns

- Nothing; the control repository holds the artifacts and the record.

# Requirements

- [FR-SDLC-001: Approved artifact chain](../requirements/functional/FR-SDLC-001.md)
- [FR-SDLC-013: Team control repository](../requirements/functional/FR-SDLC-013.md)
- [FR-CONN-004: System connections](../requirements/functional/FR-CONN-004.md)
- [NFR-ARCH-003: Self-contained components](../requirements/non-functional/NFR-ARCH-003.md)

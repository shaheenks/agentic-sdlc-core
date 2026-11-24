---
type: Non-Functional Requirement
title: "Self-contained components"
description: "Each deployable component lives in its own root folder and builds and tests on its own, with dependency URLs from environment variables."
tags: [requirement, architecture]
status: draft
x-area: ARCH
x-priority: must
x-implementation: planned
---

# Statement

The system shall keep each deployable component in its own root folder, buildable and testable on its own, and
take the URLs of the services it depends on from environment variables.

# Acceptance criteria

- Each component folder has its own dependency manifest, container build, tests and README listing its
  environment variables.
- Building and testing a component needs only its own folder (and declared library dependencies).
- No component imports code from another component's folder. Shared code is a library component, itself
  self-contained, used as a declared dependency.
- Every dependent service URL is an environment variable; none is hard-coded.

# Notes

Root folders so far: `sdlc_ui/`, `mcp_servers/` (with `user_agent_mcp/` and `event_agent_mcp/`, each a
component of its own), `a2a_router/`, `interactive_agents/` (user_agent), `event_based_agents/` (ci_workflow_agent, operations_agent),
`knowledge_search/`, `knowledge_ingest/`, `event_gateway/`, `code_workspace/`, `config/`,
`infra/`; shared libraries under `libs/`. Each component concept names its folder
in `x-folder`.

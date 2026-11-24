---
type: Functional Requirement
title: "Tool groups per surface"
description: "Each surface sees only the tool groups declared for it, on top of the user's own permissions."
tags: [requirement, authorization]
status: draft
x-area: AUTHZ
x-priority: must
x-implementation: planned
---

# Statement

The system shall declare, for each surface that calls an MCP server, which tool groups it may use, and list or
allow a tool only when both the surface and the user may use it.

# Acceptance criteria

- Tool groups and the surfaces that may use each are declared in configuration; a surface with no declaration
  gets no tools.
- The surface is identified by the OAuth client the user's token was issued to.
- Example: agents on Agent Runtime get the artifact and connection tools; coding harnesses such as Google Antigravity get the workflow
  tools and read access to the user's own artifacts.
- A call to a tool outside the surface's groups is denied and audited, even when the user could use it from
  another surface.

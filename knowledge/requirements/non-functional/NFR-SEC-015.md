---
type: Non-Functional Requirement
title: Layered access control on Google Cloud
description: On Google Cloud, IAP, Cloud Run IAM and Agent Gateway add perimeter, workload and tool layers in front of the per-user authorization in the MCP server, each failing closed and none granting more than config.
area: Security
tags:
- requirement
- non-functional
- security
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-13T12:56:17+05:30'
priority: should
implementation: built
sources:
- id: design
  resource: ../../../docs/designs/gcp-native-hosting.md
  title: GCP-native hosting design
- id: change
  resource: ../../changes/CH-0015.md
  title: CH-0015 Agent Registry and Agent Gateway for the native stack
---

# Statement

The system shall enforce access on Google Cloud in layers: who may open the UI, which identity may call the
agent and the MCP server, which tools that identity may use, and what each user may do and read. Every layer
fails closed, and no layer grants more than `config/` declares.

# Acceptance criteria

- IAP admits only members of the configured Cloud Identity group to the UI.
- The UI refuses a request whose Entra token belongs to another user than the IAP identity.
- Only the user agent's identity (and the UI service account, for its proxied routes) can invoke the MCP server.
- The gateway's MCP tool allowlist is generated from `config/tools.yaml`; a tool outside it is refused.
- Per-user authorization, team scoping and row-level security stay in the MCP server and Postgres, unchanged.

# Notes

Added by CH-0015 (design decision D17). The per-user layer is FR-AUTHZ-001 to FR-AUTHZ-006.

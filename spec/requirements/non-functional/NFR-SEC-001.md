---
type: Non-Functional Requirement
title: "Authorization only in the platform's services"
description: "Authorization is decided by the Access Policy and enforced by the services that own the resources, never in prompts, agents or the UI."
tags: [requirement, security]
status: draft
x-area: SEC
x-priority: must
x-implementation: planned
---

# Statement

The system shall decide authorization only in the Access Policy and enforce it in the services that own each resource, never in prompts, agent code or the UI.

# Acceptance criteria

- Removing a check from the UI or an agent grants no extra access.
- Agents hold no data-store or downstream credentials.

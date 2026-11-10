---
type: Non-Functional Requirement
title: Deny by default
description: Nothing is allowed unless a rule grants it, and a deny wins over any allow.
area: Security
tags:
- requirement
- non-functional
- security
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:30:44+05:30'
sources:
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

The system shall refuse anything no rule grants, and a deny shall win over any allow.

# Acceptance criteria

- A user with no matching grant sees no tools, skills or data beyond the minimal signed-in role.
- A deny rule overrides an allow from any other team or role.

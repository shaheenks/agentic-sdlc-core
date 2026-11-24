---
type: Non-Functional Requirement
title: "Deny by default, fail closed"
description: "Anything not granted is denied, and unverifiable identity or configuration denies."
tags: [requirement, security]
status: draft
x-area: SEC
x-priority: must
x-implementation: planned
---

# Statement

The system shall deny any action not explicitly granted, and deny all actions when identity or configuration cannot be verified.

# Acceptance criteria

- With no grant for an action, the action is denied.
- If the identity provider's keys or the configuration bundle cannot be loaded or verified, requests are refused.

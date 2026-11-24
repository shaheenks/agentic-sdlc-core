---
type: Non-Functional Requirement
title: "Outbound host allowlist"
description: "Components call only the external hosts declared for them."
tags: [requirement, security]
status: draft
x-area: SEC
x-priority: must
x-implementation: planned
---

# Statement

The system shall make outbound calls only to hosts declared in configuration.

# Acceptance criteria

- A call to an undeclared host is refused before any connection is made.

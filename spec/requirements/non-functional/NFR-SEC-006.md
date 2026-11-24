---
type: Non-Functional Requirement
title: "Least-privilege service identities"
description: "Each component runs as its own service account with only the roles it needs."
tags: [requirement, security]
status: draft
x-area: SEC
x-priority: must
x-implementation: planned
---

# Statement

The system shall run each component under its own Google Cloud service account, granted only the IAM roles it needs.

# Acceptance criteria

- No two components share a service account.
- No service account has a basic role (Owner, Editor, Viewer).
- The system identity of unattended runs ([FR-IDN-004](../functional/FR-IDN-004.md)) is the service account of the event agents' own Agent Runtime deployment, used by no other component.

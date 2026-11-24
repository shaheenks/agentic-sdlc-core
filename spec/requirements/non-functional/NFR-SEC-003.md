---
type: Non-Functional Requirement
title: "Tokens stay server side"
description: "User tokens never reach the browser and are never logged or stored beyond need."
tags: [requirement, security]
status: draft
x-area: SEC
x-priority: must
x-implementation: planned
---

# Statement

The system shall keep user tokens on the server, and never log them or store them longer than the work that needs them.

# Acceptance criteria

- The browser holds only a secure, HTTP-only, same-site session cookie.
- No log, trace or audit record contains a token.

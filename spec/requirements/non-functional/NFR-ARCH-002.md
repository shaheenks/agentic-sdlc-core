---
type: Non-Functional Requirement
title: "Hostnames and service URLs are configuration"
description: "No hostname or URL is hard-coded; dependent service URLs come from environment variables."
tags: [requirement, architecture]
status: draft
x-area: ARCH
x-priority: must
x-implementation: planned
---

# Statement

The system shall take every hostname and URL, its own and those of the services it calls, from environment
variables or configuration, never from code.

# Acceptance criteria

- The same image runs in every environment, and locally, with only environment variables and configuration changed.
- Each component's README lists the environment variables it reads, one per dependent service URL.

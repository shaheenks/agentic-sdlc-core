---
type: Non-Functional Requirement
title: "99.5% availability"
description: "sdlc_ui, the A2A router, user_agent_mcp, the Gemini Enterprise agent and the workflow engine are available 99.5% of each month in production."
tags: [requirement, reliability]
status: draft
x-area: REL
x-priority: must
x-implementation: planned
---

# Statement

The system shall keep sdlc_ui, the A2A router, user_agent_mcp, the Gemini Enterprise agent and the workflow engine available 99.5% of each calendar month in production.

# Acceptance criteria

- Availability is measured per surface from uptime checks and the ratio of successful requests, and reported monthly.
- The Gemini Enterprise app itself is Google's service and is excluded; the platform's agent deployment is included.

# Notes

99.5% allows about 3 hours 40 minutes of downtime in a 31-day month.

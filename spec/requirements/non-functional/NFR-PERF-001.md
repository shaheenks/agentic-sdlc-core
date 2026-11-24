---
type: Non-Functional Requirement
title: "Application response under 5 seconds on average"
description: "Requests to the platform's application components are answered in under 5 seconds on average; agent responses are excluded."
tags: [requirement, performance]
status: draft
x-area: PERF
x-priority: must
x-implementation: planned
---

# Statement

The system shall answer requests to its application components in under 5 seconds on average, measured per
calendar month in production.

# Acceptance criteria

- Application components are sdlc_ui (its pages and BFF API), the A2A router's protocol operations
  (agent card, task status, cancel, artifact fetch), user_agent_mcp's operations (initialize, tool list
  and its tool calls), and the catalog, run, task and artifact APIs behind them.
- Agent responses are excluded: model reasoning, an agent's reply in Gemini Enterprise or over A2A, and the
  time a run takes to progress or finish.
- Starting a run counts until the run is accepted and its ID returned, not until its first agent output.
- The average is measured per component per month from server-side latency metrics.

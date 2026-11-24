---
type: Functional Requirement
title: "Usage limits"
description: "Usage is held in check by approximate rate limits on tool calls at the MCP servers; token and cost budgets come later."
tags: [requirement, models]
status: draft
x-area: MDL
x-priority: should
x-implementation: planned
---

# Statement

The system shall limit usage with approximate rate limits on tool calls, enforced at the MCP servers per user and team as configuration declares.

# Acceptance criteria

- user_agent_mcp and event_agent_mcp count tool calls per user (or system identity) and team per period, per service instance, so limits are approximate ([FR-AUTHZ-005](FR-AUTHZ-005.md)).
- A call over a limit is refused with a reason the surface can show, and audited.
- Model token use is reported from Cloud Monitoring metrics; no token or cost budget is enforced.

# Notes

Exact metering and token or cost budgets wait for an operations database ([DEC-0003](../../decisions/DEC-0003.md)).

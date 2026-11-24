---
type: Functional Requirement
title: "Results of unattended runs go back to the systems involved"
description: "A scheduled or event-triggered run delivers its results to the downstream systems it serves, such as a comment on the pull request that started it."
tags: [requirement, trig, triggers]
status: draft
x-area: TRIG
x-priority: must
x-implementation: planned
---

# Statement

The system shall deliver the results of every scheduled or event-triggered run to the downstream systems that the workflow declares, through system connections, and keep no result that only a platform user could see.

# Acceptance criteria

- Each unattended workflow declares where its results go (for example a comment or review on the pull request that raised the event, a ticket update, a page); a workflow without a declared target cannot be triggered.
- Results are written through event_agent_mcp with a system connection, as write tools. Unattended workflows contain no human tasks ([FR-IDN-004](FR-IDN-004.md)), so each write they make is declared in configuration as allowed without approval ([FR-HUM-005](FR-HUM-005.md)).
- The delivery records the downstream link it created, in the run's session and audit record.
- A failed delivery fails the run's last step visibly in the audit log and is retried as the step declares.
- Intermediate artifacts under `artifacts/system/` are deleted after 7 days like any artifact.

# Notes

Unattended runs are not visible on any user's surface ([FR-AUTHZ-008](FR-AUTHZ-008.md)); people see their results where they work.

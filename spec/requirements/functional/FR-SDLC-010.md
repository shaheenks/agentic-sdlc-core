---
type: Functional Requirement
title: "Incident and bug reporting"
description: "operations_agent records incidents and bugs from diagnosed alerts and failed deployments, so they can re-enter the flow as new features and stories."
tags: [requirement, sdlc, agents]
status: draft
x-area: SDLC
x-priority: must
x-implementation: planned
---

# Statement

The system shall have operations_agent create or update an incident or bug record from a diagnosed alert or a failed deployment, in a form a user can start a new features-and-stories run from.

# Acceptance criteria

- The record holds a summary, impact, timeline, evidence, the suspected change and links; an open record for the same problem is updated rather than duplicated.
- It is created in the team's Jira project through the system Jira connection; Jira is the only tracker for now.
- A bug record carries what is needed to reproduce it, and a user can start features and stories from it ([FR-SDLC-002](FR-SDLC-002.md)).
- Once the incident is resolved, the agent drafts a post-incident summary into the record.
- Before an incident or bug is written to Jira, it is committed as a `records/` file on the team's control
  repository, and the created keys are added after the write ([DEC-0012](../../decisions/DEC-0012.md) (accepted)).

# Notes

Closes the loop: findings re-enter the flow as new work, as the playbook describes.

# Citations

[1] [The AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook)

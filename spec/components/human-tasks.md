---
type: Component
title: "Human Tasks"
description: "Pauses a run for its own user - an approval, a review, a missing input - and resumes the run with the answer, using ADK human input nodes."
tags: [component, execution, workflow]
status: draft
x-layer: execution
x-folder: interactive_agents/user_agent/
x-depends-on: [/components/access-policy, /components/workflow-engine, /components/audit-log]
x-satisfies: [/requirements/functional/FR-SURF-001, /requirements/functional/FR-SURF-003, /requirements/functional/FR-HUM-001, /requirements/functional/FR-HUM-002, /requirements/functional/FR-HUM-003, /requirements/functional/FR-HUM-004, /requirements/functional/FR-HUM-005, /requirements/functional/FR-CONN-002, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-ARCH-005, /requirements/non-functional/NFR-AUD-001, /requirements/non-functional/NFR-PERF-001, /requirements/functional/FR-SDLC-002, /requirements/functional/FR-SDLC-003]
---

# Purpose

SDLC work has gates: a lead approves a design, an author accepts generated stories before they go to Jira.
Human tasks make those gates explicit nodes of a workflow graph ([DEC-0004](../decisions/DEC-0004.md)).

# Responsibilities

- Create a task from a human input node: kind (approve, review, provide input, choose), what the person sees, the
  form of the answer; the assignee is always the run's own user, and there is no due time.
- Accept an answer only from the run's own user.
- List a user's inbox: their own runs waiting on their input.
- Notify assignees of a new task; no reminders, escalation or expiry for now.
- Record the decision, who made it and their comment; resume the graph with the answer.
- Separation of duties is parked with team assignment ([FR-HUM-004](../requirements/functional/FR-HUM-004.md)).

# Out of scope

- Delivery channels themselves (email, chat), which are connectors or notification providers.

# Interfaces

- Provides: inbox, get task, answer task; task events.
- Consumes: human input requests from the graph; memberships.

# Depends on

- [Access Policy](access-policy.md)
- [Workflow Engine](workflow-engine.md)
- [Audit Log](audit-log.md)

# Owns

- Pending input requests and answers, held in the run's Agent Runtime session ([DEC-0003](../decisions/DEC-0003.md)).

# Requirements

- [FR-SURF-001: Custom UI](../requirements/functional/FR-SURF-001.md)
- [FR-SURF-003: Gemini Enterprise app](../requirements/functional/FR-SURF-003.md)
- [FR-HUM-001: Human tasks pause a run](../requirements/functional/FR-HUM-001.md)
- [FR-HUM-002: Task routing](../requirements/functional/FR-HUM-002.md)
- [FR-HUM-003: Task signals inside the platform](../requirements/functional/FR-HUM-003.md)
- [FR-HUM-004: Separation of duties](../requirements/functional/FR-HUM-004.md)
- [FR-HUM-005: Approval before writes](../requirements/functional/FR-HUM-005.md)
- [FR-CONN-002: Reconnect instead of fail](../requirements/functional/FR-CONN-002.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-ARCH-005: Google ADK agents and graph workflows](../requirements/non-functional/NFR-ARCH-005.md)
- [NFR-AUD-001: Audit every decision](../requirements/non-functional/NFR-AUD-001.md)
- [NFR-PERF-001: Application response under 5 seconds on average](../requirements/non-functional/NFR-PERF-001.md)
- [FR-SDLC-002: Features and user stories in Jira](../requirements/functional/FR-SDLC-002.md)
- [FR-SDLC-003: Design specification from approved Jira items](../requirements/functional/FR-SDLC-003.md)

# Realisation

- ADK human input nodes (`RequestInput`), in folder `interactive_agents/user_agent/`.
- Tasks are answered in sdlc_ui and, for runs started from Gemini Enterprise, also in that conversation: the A2A
  router reports the task as *input-required*, with a link to the sdlc_ui preview for long documents. The only
  answers from outside the platform are approvals in Jira (a status transition), Confluence (a page approval, once the Confluence connector exists) and
  Git (a pull request approval or merge), where a step declares one.
- Waiting tasks are signalled inside the platform only: a count on the sdlc_ui inbox, and a "waiting for you"
  list when the user opens the chat in sdlc_ui or starts a new Gemini Enterprise conversation. Nothing is sent
  outside the platform, and there are no reminders. Findings reach people as Jira tasks ([FR-SDLC-012](../requirements/functional/FR-SDLC-012.md)).

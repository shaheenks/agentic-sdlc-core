---
type: Functional Requirement
title: "Event triggers"
description: "Runs start from events in downstream systems, such as a pull request opened."
tags: [requirement, triggers]
status: draft
x-area: TRIG
x-priority: should
x-implementation: planned
---

# Statement

The system shall start runs from events in downstream systems that match the trigger subscriptions declared in configuration.

# Acceptance criteria

- Webhook deliveries are verified (signature or token) before they are processed.
- Every event is delivered to the event gateway: webhooks from GitHub, Bitbucket, Jira and Confluence, and Google Cloud events through Pub/Sub.
- The gateway triages each event by its metadata (source system and edition, event type, repository, branch or path, Jira keys, project or service) against the subscriptions declared in configuration, and routes it to the matching workflow of ci_workflow_agent or operations_agent.
- An event starts a run only when it matches a declared subscription and its filters; an event that matches none is ignored and audited.
- A repeated delivery of the same event starts at most one run (a create-if-absent object per delivery ID, [DEC-0003](../../decisions/DEC-0003.md)).
- A started run acts as the system identity and carries the event metadata ([FR-IDN-004](FR-IDN-004.md)).
- Received, matched, ignored and rejected events are audited.
- Subscriptions are declared in `subscriptions.yaml`: the workflow, the event (provider and type), filters on its
  metadata, the writes allowed without approval and the run limits. A matched delivery is handed to a Cloud Tasks
  queue and answered at once; the task starts the run on the event agents' Agent Runtime with a session ID derived
  from the delivery ID, so a retried task resumes the same run ([DEC-0015](../../decisions/DEC-0015.md)).
- The webhook endpoint is public; a delivery whose signature does not verify is refused and audited before its body
  is processed further. The endpoint that starts runs accepts only the queue's token ([DEC-0015](../../decisions/DEC-0015.md)).
- Where an environment allows it, a team member may send a simulated event from sdlc_ui; it goes through the same
  triage, deduplication and hand-off as a verified webhook ([FR-TRIG-006](FR-TRIG-006.md), [DEC-0016](../../decisions/DEC-0016.md)).

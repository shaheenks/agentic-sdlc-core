---
type: Functional Requirement
title: "CI workflow events"
description: "ci_workflow_agent handles events from CI workflows, such as a pipeline run that failed, and reports back to the systems involved."
tags: [requirement, trig, events, ci]
status: draft
x-area: TRIG
x-priority: should
x-implementation: planned
---

# Statement

The system shall run ci_workflow_agent on events from CI workflows that match the subscriptions declared in configuration, and deliver its results to the systems the event came from.

# Acceptance criteria

- Declared CI sources (for example GitHub Actions or Bitbucket Pipelines run events) reach the event gateway, which verifies and deduplicates them ([FR-TRIG-001](FR-TRIG-001.md)).
- Each matched event starts one run of ci_workflow_agent on the event agents' Agent Runtime, acting as the system identity ([FR-IDN-004](FR-IDN-004.md)).
- Results go back to the CI system or the change that triggered it, for example a comment on the pull request ([FR-TRIG-003](FR-TRIG-003.md)).
- The run's traces carry the event metadata ([NFR-OBS-003](../non-functional/NFR-OBS-003.md)).

# Notes

Which CI events and what the agent does with each (failure analysis, flaky-test notes, summaries) are declared per workflow; the first set is to be agreed.

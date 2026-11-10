---
type: Non-Functional Requirement
title: Durable event processing
description: Event workflows survive retries, duplicates, bursts and failures without double outcomes or loops.
area: Reliability
tags:
- requirement
- non-functional
- reliability
status: draft
priority: must
implementation: planned
sources:
- id: design
  resource: ../../../docs/designs/workflow-platform.md
  title: Workflow platform target design
- id: change
  resource: ../../changes/CH-0008.md
  title: CH-0008 Workflow platform design baseline
---

# Statement

Event processing shall deliver each outcome at most once per event, retry failures, and stop runaway runs and loops.

# Acceptance criteria

- A redelivered event produces no second run or outcome (dedupe key, `claim_event`).
- Failed deliveries are retried with backoff, and go to a dead-letter topic after a set number of tries.
- Each run has a timeout, a tool-call cap and a token budget.
- Events between agents carry a hop count and are dropped above a limit. A runtime never consumes its own events.
- Intake, run and delivery records share one run id.

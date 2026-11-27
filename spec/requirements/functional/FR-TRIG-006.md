---
type: Functional Requirement
title: "Simulated events"
description: "Where an environment allows it, a team member sends an event to the event agents from sdlc_ui; the gateway reads its facts from the provider, marks it simulated and runs it like a verified webhook."
tags: [requirement, triggers, events, ui]
status: draft
x-area: TRIG
x-priority: should
x-implementation: built
---

# Statement

The system shall, in environments that allow it, let a member of a team send a simulated event for that team's
subscriptions from sdlc_ui, and run it like a verified webhook delivery.

# Acceptance criteria

- Simulation is declared per environment (`simulation: {teams: [...]}` in `system.yaml`); without it, every
  simulation is refused.
- Only sdlc_ui, a declared caller of its surface, may send one, for a forwarded user who is a member of the team the
  event is for; anyone else is refused and audited.
- The user picks one of the team's subscriptions, of any event agent, and names the subject. For a pull request event
  this is the repository, the number and the action, and the gateway reads the base branch, merge state and
  merged-by from the provider. Other event kinds are given as metadata.
- The event goes through the same triage, deduplication and Cloud Tasks hand-off as a webhook
  ([FR-TRIG-001](FR-TRIG-001.md)), with a delivery ID `sim-` plus a hash of the event's facts (for a pull
  request: repository, number, action and merge commit), so simulating the same event again starts no second run.
- The audit record and the run's state carry `simulated: true` and the user who sent it. The run still acts as the
  system identity, and every approval is still checked on the systems themselves.

# Notes

Decided in [DEC-0016](../../decisions/DEC-0016.md) (accepted), until the webhooks are set up.

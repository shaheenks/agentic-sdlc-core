---
type: Functional Requirement
title: Deploy and maintain workflows
description: Operational events start read-only diagnosis whose findings become incident records, with optional proposed fixes.
area: Workflows
tags:
- requirement
- functional
- workflows
status: draft
priority: should
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

The system shall diagnose operational events read-only and deliver each finding as an incident record, proposing a fix only when the workflow's tier allows it.

# Acceptance criteria

- A Trigger on an alert or log rule starts the workflow. An alert that opens and closes produces one finding per state.
- Diagnosis correlates logs, recent deploys and changes, and runbooks from the knowledge graph, without changing any system.
- The finding is delivered as declared on the Workflow: either a Jira ticket in the team's project (analysis, evidence links, suggested action), or an alert to the platform admins with the analysis, so that they can log the change ticket.
- A finding can start a plan-and-design workflow as its intent.
- At tier `propose`, a runbook step or fix PR is attached for a human to approve. No production change is made without a named approval.

# Notes

Delivery decided 2026-11-11 (design D1). The Jira project and issue type per team, and the admin alert channel, are open (design D8).

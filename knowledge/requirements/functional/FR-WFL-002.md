---
type: Functional Requirement
title: Event intake
description: One gateway receives CI and operational events, verifies the caller, matches a Trigger and publishes a normalised event.
area: Workflows
tags:
- requirement
- functional
- workflows
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

The system shall receive events from CI tools and operational platforms through one intake that verifies each caller and accepts only events that match a declared Trigger.

# Acceptance criteria

- CI adapters: GitHub (Actions and PR webhooks), and Bitbucket Cloud and Data Center (Pipelines and PR webhooks). Ops adapters: GCP Cloud Monitoring, on-premise Kubernetes and Splunk, all pushing to the gateway's endpoint. Pulling from these systems is out of scope for now (design D3).
- A forged signature, an unknown caller or a disabled Trigger is refused, publishes nothing, and is audited as `event_intake` without the payload.
- Accepted events are published as CloudEvents 1.0, with a size-capped summary and links instead of the full payload.
- The gateway is the only public intake for events and reads only the `Trigger` config kind.

# Notes

Design: version-03 P6 (R1 to R5) and the target design, section 5.

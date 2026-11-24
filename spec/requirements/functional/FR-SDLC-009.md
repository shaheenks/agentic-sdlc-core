---
type: Functional Requirement
title: "Alert triage and log analysis"
description: "operations_agent diagnoses alerts read-only from logs, metrics, traces and recent changes, and posts the diagnosis with evidence."
tags: [requirement, sdlc, agents]
status: draft
x-area: SDLC
x-priority: must
x-implementation: planned
---

# Statement

The system shall have operations_agent diagnose each alert read-only from logs, metrics, traces and recent deployments, and post the diagnosis with its evidence.

# Acceptance criteria

- A Cloud Monitoring alert delivered through Pub/Sub starts the run.
- The diagnosis reads logs, metrics, traces and recent deployments and changes; it changes nothing.
- The result states the suspected cause, the evidence, the likely related change and a suggested next step, posted to the incident or bug record, with a Jira task when action is needed ([FR-SDLC-012](FR-SDLC-012.md)).
- Remediation runs only as a runbook declared in configuration as pre-approved for that environment; none is declared for now.
- The first alerts: Cloud Run 5xx error rate, Cloud Run p95 latency above 5 s, Cloud Build failures, Cloud Deploy rollout failures, and Cloud Run job failures, on the platform's own services in development.

# Notes

Corresponds to the playbook's Maintain stage: read-only diagnosis first, actions only from approved runbooks.

# Citations

[1] [The AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook)

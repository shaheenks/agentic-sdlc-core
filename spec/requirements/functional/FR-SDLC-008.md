---
type: Functional Requirement
title: "Deployment handling"
description: "operations_agent follows builds and deployments, reports their outcome where the change came from, checks health after a rollout, and explains failures."
tags: [requirement, sdlc, agents]
status: draft
x-area: SDLC
x-priority: must
x-implementation: planned
---

# Statement

The system shall have operations_agent follow build and deployment events, report each outcome back to the change it came from, check service health after a rollout and explain failures.

# Acceptance criteria

- Build and deployment events (Cloud Build, Cloud Deploy, Cloud Run revisions) start the run ([FR-TRIG-005](FR-TRIG-005.md)).
- The outcome is posted on the pull request, ticket or release the deployment belongs to.
- After a rollout it compares error rate and latency with the period before, and reports the result.
- On a failure it reads the build or deploy logs and posts the likely cause with evidence.
- It runs only actions declared in configuration for that environment; none are declared for now, so it reports   only (a rollback in development is the first candidate); anything else is left to people.

# Notes

Corresponds to the playbook's Deploy stage, with autonomy tiered by environment.

# Citations

[1] [The AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook)

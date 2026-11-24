---
type: Functional Requirement
title: "Quality assurance analysis of pull requests"
description: "A ci_workflow_agent workflow of its own analyses each pull request in a declared repository for quality and posts the findings; people approve and merge."
tags: [requirement, sdlc, agents]
status: draft
x-area: SDLC
x-priority: must
x-implementation: planned
---

# Statement

The system shall run a quality assurance analysis workflow on ci_workflow_agent for each pull request in a declared repository, and post its findings on the pull request without approving or merging it.

# Acceptance criteria

- It is its own workflow, with its own trigger subscription, skills and configuration, separate from security vulnerability analysis ([FR-SDLC-007](FR-SDLC-007.md)); the two can run on the same pull request in parallel.
- A pull request opened or updated in a declared repository starts it, including pull requests the agent opened itself.
- It checks correctness, test coverage of the change and of each user story's acceptance criteria, maintainability, and conformance to `plan.md`, the design specification and the team's quality skills.
- A pull request without the Jira key of a user story or feature is reported as a finding.
- Results of deterministic checks from CI (tests, linters, coverage) are included and not repeated.
- Findings are posted as review comments with a severity and a short summary; minor style comments are capped. It runs in a fresh context and is never the run that wrote the code.
- Findings at or above the declared severity are also raised as a Jira task ([FR-SDLC-012](FR-SDLC-012.md)).
- It never approves or merges; the merge needs human approval under branch protection.

# Notes

Corresponds to the playbook's layered agentic review, with people approving.

# Citations

[1] [The AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook)

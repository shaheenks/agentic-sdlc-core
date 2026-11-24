---
type: Functional Requirement
title: "Security vulnerability analysis of pull requests"
description: "A ci_workflow_agent workflow of its own analyses each pull request in a declared repository for security vulnerabilities and posts the findings; people approve and merge."
tags: [requirement, sdlc, agents]
status: draft
x-area: SDLC
x-priority: must
x-implementation: planned
---

# Statement

The system shall run a security vulnerability analysis workflow on ci_workflow_agent for each pull request in a declared repository, and post its findings on the pull request without approving or merging it.

# Acceptance criteria

- It is its own workflow, with its own trigger subscription, skills and configuration, separate from quality assurance analysis ([FR-SDLC-011](FR-SDLC-011.md)); the two can run on the same pull request in parallel.
- A pull request opened or updated in a declared repository starts it, including pull requests the agent opened itself.
- It checks for exposed secrets, authentication and authorization flaws, injection and input validation, unsafe data handling, and vulnerable or unapproved dependencies, against the team's security policy skills.
- Results of deterministic security checks from CI (secret scanners, dependency and static analysis) are included and not repeated.
- Each finding has a severity, its location, the evidence and a suggested fix; it runs in a fresh context and is never the run that wrote the code.
- Findings at or above the declared severity are also raised as a Jira task ([FR-SDLC-012](FR-SDLC-012.md)).
- It never approves or merges; the merge needs human approval under branch protection.

# Notes

Corresponds to the playbook's layered agentic review, with people approving.

# Citations

[1] [The AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook)

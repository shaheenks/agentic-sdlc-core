---
type: Functional Requirement
title: "Approved artifact chain"
description: "Each stage of the SDLC flow ends with an approved artifact in its system of record (Jira for features and stories, the repository from the design on), and the next stage starts from it."
tags: [requirement, sdlc, agents]
status: draft
x-area: SDLC
x-priority: must
x-implementation: planned
---

# Statement

The system shall run its SDLC flow as a chain of artifacts, where each stage ends with an artifact that a person approves and that is recorded in its system of record, and the next stage starts by reading that artifact.

# Acceptance criteria

- The stages and their artifacts: features and user stories (Jira issues), the design specification (a pull request in the respective repository), the implementation plan (`plan.md`), code with tests (a pull request), security and quality findings (pull request comments), and incident or bug records (tracker issues).
- Each artifact names the artifacts it was made from and the run that made it.
- Approval is recorded: as the user's confirmation in chat for features and stories and for the design specification, and as a merge under the repository's branch protection for repository stages.
- Jira is the source of truth for features and user stories; the repository is the source of truth from the design specification on. Each repository artifact names its Jira keys, and the Jira issues link back to the pull request.
- No agent approves or merges an artifact that it produced.
- Every pull request the agents open (design, plan and implementation) carries the Jira keys of the user stories it delivers, or of the feature when it covers the whole feature, in its title, description and branch name; the Jira issues link back to it.

# Notes

Follows the playbook's *committed artifact* pattern: each accepted artifact starts the next stage, and people concentrate at the gates. The hand-off between user_agent and the event-based agents is [DEC-0008](../../decisions/DEC-0008.md) (accepted).

# Citations

[1] [The AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook)

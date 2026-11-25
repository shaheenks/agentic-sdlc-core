---
type: Functional Requirement
title: "Implementation by ci_workflow_agent"
description: "ci_workflow_agent turns a merged design specification into an implementation plan and, once the plan is merged, into a pull request with code and tests."
tags: [requirement, sdlc, agents]
status: draft
x-area: SDLC
x-priority: must
x-implementation: planned
---

# Statement

The system shall have ci_workflow_agent implement a merged design specification: first as an implementation plan proposed for approval, then, once the plan is merged, as a pull request with code and tests.

# Acceptance criteria

- A merge of `design.md` on the team's control repository starts the run; the feature's Jira status does not matter.
- The agent works in every target repository the specification names, each with its own plan and implementation pull requests.
- The agent first proposes `plan.md` as a pull request: files that change, order of work, risks, and how the change will be proven (tests). Nothing is implemented without a merged plan.
- Once the plan is merged, the agent implements it on a new branch with tests (for a bug fix, a failing test first), lets the repository's CI run the build and tests, and fixes failures within the run's limits ([FR-WFL-005](FR-WFL-005.md)).
- It opens a pull request tagged with the Jira keys of the user stories it delivers ([FR-SDLC-001](FR-SDLC-001.md)), linking the design specification and the plan, and updates `plan.md` in the same pull request where the implementation departs from it.
- It never merges, approves or pushes to a protected branch; people review and merge.
- If the plan cannot be built as written, or open questions block it, the agent comments on the pull request and stops rather than guessing.
- It acts as the system identity through event_agent_mcp with system connections; its writes are declared as allowed without approval ([FR-TRIG-003](FR-TRIG-003.md)), because approval happens at the merge.
- The design and plans come from the team's control repository ([FR-SDLC-013](FR-SDLC-013.md)): a merge of
  `design.md` starts the run, and each plan is proposed as `plan-<repo>.md` by pull request there; implementation
  pull requests are opened only after the plan is approved, and their links are recorded in `links.yaml`
  ([DEC-0012](../../decisions/DEC-0012.md) (accepted)).

# Notes

Corresponds to the playbook's Build stage (plan mode, `plan.md`, then implementation). The agent edits code and runs tests in the [Code Workspace](../../components/code-workspace.md), a Cloud Run job.

# Citations

[1] [The AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook)

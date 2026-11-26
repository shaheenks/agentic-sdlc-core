---
type: Functional Requirement
title: "Approved artifact chain"
description: "Every artifact an agent's write to Jira, Confluence or a repository rests on is approved in the team's sdlc-control repository, by a person merging its pull request, before the write; the next stage starts from it."
tags: [requirement, sdlc, agents]
status: draft
x-area: SDLC
x-priority: must
x-implementation: planned
---

# Statement

The system shall run its SDLC flow as a chain of artifacts in which every write by an agent to Jira, Confluence or a
product repository rests on an artifact approved in the team's control repository, and a stage that starts from a
published artifact checks that it is approved there.

# Acceptance criteria

- The artifacts: features and user stories (`feature.md`), the design specification (`design.md`), the
  implementation plan per target repository (`plan-<repo>.md`), and, for unattended runs, the record of each write
  (`records/`); the layout is [FR-SDLC-013](FR-SDLC-013.md).
- Drafts stay the user's own artifacts ([FR-ART-001](FR-ART-001.md)) for as long as the user wants; a step that
  continues from the user's own artifact checks nothing on the control repository.
- An artifact is approved when it is on the control repository's main branch and the last commit that changed it
  there came from a pull request merged by a person, not by a system identity. No agent approves or merges an
  artifact it produced.
- The MCP server, not the agent, makes the check: a tool that writes to Jira, Confluence or a product repository
  takes the artifact's control ID and refuses the write unless it is approved and belongs to the run's team.
- A step that starts from a published artifact (a Jira feature, a merged design, a merged plan) checks it on the
  control repository's main branch first.
- The results of each write (Jira keys, Confluence pages, pull requests) are recorded next to the artifact.
- Every pull request the agents open carries the Jira keys of the stories it delivers, or of the feature, in its
  title, description and branch name; the Jira issues link back to it.
- A feature and its stories are approved by the user in chat: the approval is recorded by committing `feature.md`
  (with who approved and when) to the feature's branch `feature/<control-id>` on the control repository, before any
  Jira write. Every later artifact (design, plans) reaches that branch by a pull request; approved means merged into
  the feature branch by a person, and the check is made against the feature branch, not main ([DEC-0013](../../decisions/DEC-0013.md)).

# Notes

Follows the playbook's *committed artifact* pattern. Decided in [DEC-0012](../../decisions/DEC-0012.md) (accepted), which replaces the hand-off of
[DEC-0008](../../decisions/DEC-0008.md).

# Citations

[1] [The AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook)

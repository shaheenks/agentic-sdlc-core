---
type: Functional Requirement
title: "Design specification hand-off"
description: "When the user hands a design specification to implementation, user_agent opens a pull request with it as design.md on the team's control repository, as the user; a person merging it approves it and approves it for the implementation plan."
tags: [requirement, sdlc, agents]
status: draft
x-area: SDLC
x-priority: must
x-implementation: built
---

# Statement

The system shall, when the user hands a design specification to implementation, have user_agent open a pull request
with it on the team's control repository with the user's own connection; merging it is the approval and the
hand-off.

# Acceptance criteria

- The pull request adds `features/<control-id>/design.md` on the team's control repository; if the feature is not
  published yet, `feature.md` comes in the same pull request.
- Its title, description and branch name carry the feature's Jira keys when they exist; the description lists the
  review findings and what the user decided about them, and the sources used.
- It is opened with the user's own connection ([FR-CONN-001](FR-CONN-001.md)), so the commit is the user's.
- A person merging it under the control repository's branch protection approves it; user_agent's implementation
  plan starts from the merged design ([FR-SDLC-006](FR-SDLC-006.md), [DEC-0016](../../decisions/DEC-0016.md)).
- The design is not opened as a pull request on a product repository.
- The event-based agents never read the user's artifact store; the control repository and Jira are their only
  channels ([FR-AUTHZ-008](FR-AUTHZ-008.md)).
- The pull request goes into the feature's branch `feature/<control-id>`, not main; a person merging it into the
  feature branch approves it and hands it on. A design needs its feature approved and opened first ([DEC-0013](../../decisions/DEC-0013.md)).

# Notes

Decided in [DEC-0012](../../decisions/DEC-0012.md) (accepted), which replaces the design pull request of [DEC-0008](../../decisions/DEC-0008.md).

# Citations

[1] [The AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook)

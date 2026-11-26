---
type: Functional Requirement
title: "Features and user stories"
description: "user_agent drafts a feature and its user stories with the user as the user's own artifact; when the user asks to add them to Jira, the draft goes to the team's control repository, and once a person merges it the Jira issues are created as the user and recorded."
tags: [requirement, sdlc, agents]
status: draft
x-area: SDLC
x-priority: must
x-implementation: built
---

# Statement

The system shall let user_agent draft a feature and its user stories with the user and, when the user asks to add
them to Jira and the draft is approved in the team's control repository, create them in Jira with the user's own
connection.

# Acceptance criteria

- The starting point is an idea in conversation, a ticket, or a bug or incident record ([FR-SDLC-010](FR-SDLC-010.md)).
- Before drafting, user_agent asks about the problem, the users affected, scope, constraints, how success is measured
  and open questions; a brainstorm step can first produce a short brief.
- Drafts are grounded in knowledge search within the run's team scope, citing sources ([FR-KNOW-004](FR-KNOW-004.md)).
- The feature has a high-level estimate (a T-shirt size, XS to XL, with what it means for the team) and each story
  has story points (1, 2, 3, 5, 8 or 13; 13 means split it); in Jira the size is a `size-<S>` label and a line in the
  description, and the points go into the project's story points field (found by name, or `story_points_field` in
  the team's configuration) and into the description.
- The draft is one feature with three to eight user stories ("As a ..., I want ..., so that ...") with acceptance
  criteria, plus open questions; it is saved as the user's artifact ([FR-ART-001](FR-ART-001.md)), and the user can
  keep it there and go on to the design with it.
- The user can have it reviewed by fresh-context reviewers ([FR-SDLC-004](FR-SDLC-004.md)).
- While drafting, user_agent searches the team's Jira project for open epics, features and stories and names them
  in the draft: the epic the feature belongs to, an open feature it extends, open stories it would duplicate. If no
  open epic fits, it proposes one, created only on the user's confirmation ([DEC-0013](../../decisions/DEC-0013.md)).
- On the user's approval in chat (choosing the epic), the feature's branch opens on the control repository with the
  approval recorded, then the Jira issues are created as the user: the Epic (if confirmed), the Feature under it, and
  each user story as a sub-task of the Feature with its story points; open issues with the same summary are reused.
  The keys are recorded on the feature branch, and the feature branch opens on the target repositories.

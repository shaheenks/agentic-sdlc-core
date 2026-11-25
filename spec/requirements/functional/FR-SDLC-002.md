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
- The draft is one feature with three to eight user stories ("As a ..., I want ..., so that ...") with acceptance
  criteria, plus open questions; it is saved as the user's artifact ([FR-ART-001](FR-ART-001.md)), and the user can
  keep it there and go on to the design with it.
- The user can have it reviewed by fresh-context reviewers ([FR-SDLC-004](FR-SDLC-004.md)).
- When the user asks to add it to Jira, user_agent opens a pull request with it as `feature.md` on the team's control
  repository, with the user's own connection, and waits; once a person has merged it, it creates the Feature issue
  and its User Story issues in one of the team's Jira projects (the default unless the user names another), as the
  user, and records their keys in `links.yaml` ([FR-SDLC-013](FR-SDLC-013.md)).
- The Jira tool refuses to create issues for a `feature.md` that is not approved ([FR-SDLC-001](FR-SDLC-001.md)).
- The next runs do not depend on the feature's Jira status: a design starts from the approved feature
  ([FR-SDLC-003](FR-SDLC-003.md)), the implementation from the merged design ([FR-SDLC-006](FR-SDLC-006.md)).

# Notes

Corresponds to the playbook's Plan stage and EGM's brainstorm and draft steps. Decided in [DEC-0012](../../decisions/DEC-0012.md) (accepted).

# Citations

[1] [The AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook)
[2] [Elephant-Goldfish Model: guide](https://egm.dev/guide)

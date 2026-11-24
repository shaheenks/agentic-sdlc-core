---
type: Functional Requirement
title: "Features and user stories in Jira"
description: "user_agent drafts features and user stories with the user, from an idea, ticket or bug record, and adds them to Jira as the user once the user approves them in chat."
tags: [requirement, sdlc, agents]
status: draft
x-area: SDLC
x-priority: must
x-implementation: planned
---

# Statement

The system shall let user_agent draft features and user stories with the user and, once the user approves them in chat, add them to Jira with the user's own connection.

# Acceptance criteria

- The starting point is an idea in conversation, a ticket, or a bug or incident record ([FR-SDLC-010](FR-SDLC-010.md)).
- Before drafting, user_agent asks about the problem, the users affected, scope, constraints, how success is measured and open questions; a brainstorm step can first produce a short brief.
- Drafts are grounded in knowledge search within the run's team scope, citing sources ([FR-KNOW-004](FR-KNOW-004.md)).
- The draft lists features, each with user stories ("As a ..., I want ..., so that ...") and acceptance criteria, plus open questions; until approval it is the user's artifact ([FR-ART-001](FR-ART-001.md)).
- The user can have it reviewed by fresh-context reviewers ([FR-SDLC-004](FR-SDLC-004.md)) before approving.
- The user approves in chat ([FR-HUM-002](FR-HUM-002.md)); only then does user_agent create a Feature issue and its User Story issues in the team's Jira project, with the user's own Jira connection ([FR-CONN-001](FR-CONN-001.md)), so the user is their author. A rejection with comments returns to drafting.
- The issue types are Feature and User Story. user_agent reports the new keys; from then on the feature's Jira status allows the next runs: **In Design** for the design run and **In Development** for the development run ([FR-SDLC-003](FR-SDLC-003.md), [FR-SDLC-006](FR-SDLC-006.md)).

# Notes

Corresponds to the playbook's Plan stage, with Jira as the system of record for features and stories, and to EGM's brainstorm and draft steps.

# Citations

[1] [The AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook)
[2] [Elephant-Goldfish Model: guide](https://egm.dev/guide)

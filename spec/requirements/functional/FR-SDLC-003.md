---
type: Functional Requirement
title: "Design specification from approved Jira items"
description: "user_agent drafts a design specification from an approved Jira feature and its user stories, read with the user's own connection; it is reviewed by fresh-context reviewers and approved by the user in chat."
tags: [requirement, sdlc, agents]
status: draft
x-area: SDLC
x-priority: must
x-implementation: planned
---

# Statement

The system shall let user_agent draft a design specification from an approved Jira feature and its user stories, read on behalf of the user, have it reviewed by fresh-context reviewers, and hand it on only after the user approves it in chat.

# Acceptance criteria

- The user names a Feature (or user_agent finds it); user_agent reads it and its User Stories from Jira with the user's own connection, and starts only if the feature's Jira status is **In Design**.
- It also reads existing designs and code through knowledge search within the run's team scope ([FR-KNOW-004](FR-KNOW-004.md)).
- It names the target repositories for the code: one or more of the repositories declared for the team the run is for (a team can have several); the user confirms them.
- It covers context, goals and non-goals, the design (components, interfaces, data and flows), alternatives considered, security and privacy, the test approach, rollout and operations, risks and open questions, and maps every user story, by Jira key, to the sections that satisfy it.
- Policy skills declared for the team (for example security, architecture, compliance) are applied while drafting, and any conflict with a policy is flagged for the user.
- It is reviewed by fresh-context reviewers ([FR-SDLC-004](FR-SDLC-004.md)) before it is offered for approval.
- The user approves in chat; then user_agent opens the pull request ([FR-SDLC-005](FR-SDLC-005.md)). A rejection with comments returns to drafting.

# Notes

Corresponds to the playbook's Design stage (`spec.md`) and EGM's draft and review steps.

# Citations

[1] [The AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook)
[2] [Elephant-Goldfish Model: guide](https://egm.dev/guide)

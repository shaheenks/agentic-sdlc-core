---
type: Functional Requirement
title: "Design specification"
description: "user_agent drafts a design specification from the user's own feature artifact or from a published Jira feature and its stories; it is reviewed by fresh-context reviewers and saved as the user's artifact until the user publishes it."
tags: [requirement, sdlc, agents]
status: draft
x-area: SDLC
x-priority: must
x-implementation: built
---

# Statement

The system shall let user_agent draft a design specification from the user's own feature artifact or from a
published Jira feature and its user stories, have it reviewed by fresh-context reviewers, and keep it as the user's
artifact until the user publishes it ([FR-SDLC-005](FR-SDLC-005.md)).

# Acceptance criteria

- From the user's own feature artifact, user_agent starts without any check on the control repository.
- From a Jira feature, it reads the feature and its User Stories with the user's own connection and starts only if
  the feature's `feature.md` is approved on the team's control repository with the feature's key recorded in its
  `links.yaml`; the feature's Jira status does not matter.
- It reads existing designs and code through knowledge search within the run's team scope
  ([FR-KNOW-004](FR-KNOW-004.md)) and the team's repositories.
- It names the target repositories for the code: one or more of the team's repositories (the default unless the user
  names others); the user confirms them.
- It covers context, goals and non-goals, the design (components, interfaces, data and flows), alternatives
  considered, security and privacy, the test approach, rollout and operations, risks and open questions, and maps
  every user story to the sections that satisfy it.
- Policy skills declared for the team are applied while drafting, and any conflict with a policy is flagged.
- It is reviewed by fresh-context reviewers ([FR-SDLC-004](FR-SDLC-004.md)) and saved as the user's artifact.
- From a published feature, the feature is read from its feature branch on the control repository ([DEC-0013](../../decisions/DEC-0013.md)).

# Notes

Corresponds to the playbook's Design stage (`spec.md`) and EGM's draft and review steps. Decided in [DEC-0012](../../decisions/DEC-0012.md) (accepted).

# Citations

[1] [The AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook)
[2] [Elephant-Goldfish Model: guide](https://egm.dev/guide)

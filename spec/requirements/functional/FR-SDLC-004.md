---
type: Functional Requirement
title: "Fresh-context document review"
description: "Documents are reviewed by reviewer agents that read only the written document and permitted evidence, never the drafting conversation; the user decides which findings to apply."
tags: [requirement, sdlc, agents]
status: draft
x-area: SDLC
x-priority: must
x-implementation: planned
---

# Statement

The system shall review features, stories and design specifications with reviewer agents that read only the written document and permitted supporting material, and apply only the fixes the user approves.

# Acceptance criteria

- Each reviewer is a separate agent invocation; it receives the document and permitted evidence (knowledge search results, source code) but not the drafting conversation.
- The reviewer set is declared in configuration. The default covers structure, writing style, clarity for a new reader, design decisions, readiness to build, technical detail and unnecessary complexity; a team can add a reviewer with its own standard as a skill.
- Findings are merged and de-duplicated, each with a severity, its location and a suggested change.
- The user decides which findings to apply; user_agent applies only those.
- The review repeats until two rounds in a row find no serious problem, or until five rounds, when user_agent asks the user how to continue.
- The user picks the review depth (reviewers and rounds) per document. A review is feedback, not proof that a document is correct.

# Notes

Follows the Elephant-Goldfish Model: user_agent is the *elephant* with the whole conversation, the reviewers are *goldfish* without it. The reviewer standards can start from EGM's open-source (Apache 2.0) skills.

# Citations

[2] [Elephant-Goldfish Model: guide](https://egm.dev/guide)
[3] [Elephant-Goldfish Model: review loop](https://egm.dev/skills/egm-review-loop)

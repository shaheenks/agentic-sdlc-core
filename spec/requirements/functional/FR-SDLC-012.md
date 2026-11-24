---
type: Functional Requirement
title: "Jira tasks from findings"
description: "Findings that need someone's attention are raised as Jira tasks, linked to the user stories, feature or incident they concern; Jira is the notification channel."
tags: [requirement, sdlc, agents]
status: draft
x-area: SDLC
x-priority: must
x-implementation: planned
---

# Statement

The system shall notify people of findings by creating Jira tasks from them, linked to the user stories, feature or incident they concern.

# Acceptance criteria

- Security vulnerability analysis ([FR-SDLC-007](FR-SDLC-007.md)) and quality assurance analysis ([FR-SDLC-011](FR-SDLC-011.md)) create one Jira Task per pull request and analysis, listing the findings at or above the severity declared in configuration, linked to the pull request's user stories or feature.
- A diagnosis from alert triage or a failed deployment ([FR-SDLC-008](FR-SDLC-008.md), [FR-SDLC-009](FR-SDLC-009.md)) that needs action creates a Jira Task linked to the incident or bug record ([FR-SDLC-010](FR-SDLC-010.md)).
- A new analysis of the same pull request or problem updates the open task instead of creating another.
- Tasks go to the team's Jira project and are created through the system Jira connection.
- Jira's own notifications (assignee, watchers) reach people; the platform sends no e-mail, chat or other messages of its own.

# Notes

For now this is the only notification channel outside the platform. Human tasks waiting for a user are signalled only inside the platform: an inbox count in sdlc_ui and a waiting list when the user opens the chat or a new Gemini Enterprise conversation ([FR-HUM-003](FR-HUM-003.md)).

---
type: Functional Requirement
title: "Team control repository"
description: "Each team's sdlc-control repository holds the approved artifacts every agent write rests on and the record of those writes, in one layout the MCP servers check before writing."
tags: [requirement, sdlc, agents, audit]
status: draft
x-area: SDLC
x-priority: must
x-implementation: built
---

# Statement

The system shall keep, for each team, one control repository that holds the approved artifacts behind every agent
write to Jira, Confluence and product repositories and the record of those writes, and shall check approval there
before each such write.

# Acceptance criteria

- Each team declares one control repository per environment (`control_repo`), on GitHub or Bitbucket, cloud or Data
  Center; any `org/repo` name, and no two teams share one.
- Layout: `features/<control-id>/` with `feature.md`, `design.md`, `plan-<repo>.md` and `links.yaml`;
  `records/<yyyy>/<mm>/<run-id>.md` for unattended writes. A control ID is `F-<yyyymmdd>-<slug>`, assigned when an
  artifact is first published.
- Each artifact has front matter with its control ID, team, kind, the run that drafted it, the previous artifact's
  path and commit, and the Jira keys once they exist.
- Artifacts reach the main branch only through pull requests, opened on a branch `sdlc/<control-id>/<kind>`.
- Before opening one, the open pull requests are listed: if one is open for the same artifact (the same control ID
  and kind, or a feature of the same name), it is returned instead and no second one is opened. Likewise, before an
  agent creates a Jira issue or a Confluence page from an artifact, it searches for an existing one with the same
  title (summary) of the same type in the same project or space and uses it instead of creating a second.
- Approved means: on the main branch, and the last commit that changed the artifact there came from a pull request
  merged by a person, not by a system identity. The check returns the merge commit and who merged.
- After each write the results (keys, links, the artifact commit, the run, the acting identity, the time) are
  committed to `links.yaml` (or the run's `records/` file) directly on main; a write whose result never landed shows
  as an artifact without links.
- A user reaches the control repository with their own connection; the event-based agents with the system
  identity's.

# Notes

Decided in [DEC-0012](../../decisions/DEC-0012.md) (accepted).

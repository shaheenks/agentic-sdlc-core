---
name: design-specification
description: Draft a design specification from an approved Jira feature and its user stories, grounded in the team's existing designs and code, for review, approval and a pull request. Use in the design workflow.
---

# Design specification

Write the design that implementing engineers, and ci_workflow_agent, will build from. It is reviewed by
fresh-context reviewers, approved by the user and opened as a pull request on the team's repository.

## Inputs

- The feature and its stories, read from Jira (jira_get_issue). Use their keys everywhere.
- Existing designs, requirements and code: knowledge_search and knowledge_graph in the run's team scope, and the
  team's repositories (team_systems, repo_list, repo_read_file). Read the code the design touches.
- Policy skills declared for the team, if any: apply them and flag every conflict for the user.
- The target repositories: one or more of the team's repositories; ask the user to confirm them. The first one
  gets the pull request.

## The specification

```markdown
# <Feature key>: <feature summary>

| | |
|---|---|
| Feature | <KEY> |
| Stories | <KEY-1>, <KEY-2> |
| Target repositories | owner/name (pull request), owner/other |
| Status | Draft |

## Context
## Goals
## Non-goals
## Design
### Components
### Interfaces
### Data
### Flows
## Alternatives considered
## Security and privacy
## Test approach
## Rollout and operations
## Risks
## Open questions
## Story coverage
| Story | Sections |
|---|---|
| <KEY-1> | Design > Interfaces, Test approach |
## Sources
- [path](link)
```

Rules:

- Every story key appears in Story coverage, mapped to the sections that satisfy it. A story that no section
  satisfies is an open question, not a silent gap.
- Interfaces are concrete: names, signatures or endpoints, data shapes, errors. Decide; do not leave choices to
  the implementer.
- Prefer what exists: name the components, libraries and patterns you reuse, with links.
- State assumptions as assumptions, with how to check them.
- Save the draft as an artifact (artifact_save) and show it. Open the pull request only after approval.
- Before a pull request is raised (on the control repository or a target repository), list the open ones
  (control_pull_requests, repo_pull_requests) and do not raise a second one for the same feature or change.

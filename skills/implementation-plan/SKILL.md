---
name: implementation-plan
description: Plan how one target repository implements an approved design - the files that change, the order of work, the risks and how the change is proven - for a person to approve before any code is written. Use in ci_workflow_agent's plan workflow.
---

# Implementation plan

Write the plan for one target repository. A person reviews it and merges it into the feature branch; only then is
anything implemented, and the implementation is checked against it. Nothing is built from a plan that is not
merged.

## Inputs

- The approved design specification and the feature it is for, from the feature branch on the team's control
  repository (control_read_file: design.md, feature.md). Use the Jira keys of the feature and its stories.
- The repository's code at the feature branch (repo_list, repo_read_file with the feature branch as ref): read the
  files the design touches, the tests next to them, and the build files. Read what you need, not everything.

## The plan

```markdown
# <Feature key>: plan for <owner/repo>

| | |
|---|---|
| Design | features/<control-id>/design.md |
| Stories | <KEY-1>, <KEY-2> |
| Repository | owner/repo, branch feature/<control-id> |

## Summary
## Changes
| File | Change | Story |
|---|---|---|
| src/payments/refunds.py | New: `refund(payment_id, amount) -> Refund` | KEY-1 |
## Order of work
1. ...
## Tests
- The tests that prove each story, and where they go. For a bug fix, the failing test first.
## Risks
## Out of scope
## Open questions
```

Rules:

- Only this repository's part of the design. Name the files exactly as they are (or will be) in the repository.
- Every story the design maps to this repository appears in Changes or Tests. A story you cannot cover is an open
  question, not a silent gap.
- Prefer what exists: extend the code and test patterns the repository already uses, and say which.
- If the design leaves a choice the code needs, or contradicts the code, write it as an open question; do not
  guess. Open questions block implementation until a person answers them on the pull request.
- Small, ordered steps a reviewer can check. No code beyond short signatures.
- Return only the plan's Markdown.

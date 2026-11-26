---
name: features-and-stories
description: Draft one feature with its user stories and acceptance criteria from a brief, an idea, a ticket or a bug, grounded in the team's knowledge. Use in the features-and-stories workflow before review and approval.
---

# Features and stories

Draft the feature and its user stories that the user will approve and that become a Feature issue and its User
Story issues in the team's Jira project.

## Before drafting

- Make sure the problem, users, scope, constraints, success measure and open questions are known; if not, ask,
  or use the brainstorm skill first.
- Search the team's knowledge (knowledge_search, knowledge_graph) for related requirements, designs and code.
  Cite what you use as `[path](link)`. You see only the run's team scope; never claim knowledge you did not find.

## The draft

```markdown
# Feature: <summary, under 100 characters>

<Two to five sentences: the problem, who has it, the outcome. Link the brief or ticket it came from.>

High-level estimate: <XS | S | M | L | XL> (<what it means here, such as about 2-3 weeks for one team>): <one line on
what drives the size: the largest stories, unknowns, dependencies>.

## User stories

### <Story summary, under 100 characters>
As a <user>, I want <capability>, so that <benefit>.

Story points: <1 | 2 | 3 | 5 | 8 | 13> (<one line: the work and the risk behind the number>)

Acceptance criteria:
- Given <context>, when <action>, then <observable result>.

## Out of scope
## Open questions
## Sources
- [path](link)
```

Rules:

- One feature per draft. Three to eight stories; split a story that needs more than five acceptance criteria.
- Every story can be delivered and tested on its own; acceptance criteria are observable, never "works well".
- Estimate every story in story points on the Fibonacci scale (1, 2, 3, 5, 8, 13), relative to each other: effort,
  complexity and risk, not hours. A story of 13 is too big: split it. Ground the numbers in what you found in the
  code and knowledge; say what you assumed.
- Give the feature a high-level T-shirt size (XS, S, M, L, XL) consistent with its stories' total, with a note on
  what the size means for this team (for example, M: about 2-3 weeks for one team) and what drives it.
- Use the users' words for roles; name systems as the team's knowledge names them.
- Save the draft as an artifact (artifact_save, content type text/markdown) and show it in the chat. It stays the
  user's artifact until it is approved.
- Never create Jira issues in this step: that happens only after the user approves the draft.
- Before the draft is published, list the open pull requests on the team's control repository
  (control_pull_requests): if one is open for the same feature, point the user to it instead of a new one.

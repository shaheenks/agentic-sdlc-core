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

## User stories

### <Story summary, under 100 characters>
As a <user>, I want <capability>, so that <benefit>.

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
- Use the users' words for roles; name systems as the team's knowledge names them.
- Save the draft as an artifact (artifact_save, content type text/markdown) and show it in the chat. It stays the
  user's artifact until it is approved.
- Never create Jira issues in this step: that happens only after the user approves the draft.

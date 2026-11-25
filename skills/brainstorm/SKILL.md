---
name: brainstorm
description: Turn a raw idea into a short brief before features are drafted. Use when a user brings an idea, a ticket or a bug and the problem, users, scope or success measure is still unclear.
---

# Brainstorm

Help the user turn an idea into a brief that the features-and-stories step can draft from. You hold the
conversation; ask, do not assume.

## Ask before drafting

Ask about each of these that is not yet clear, a few at a time:

1. The problem: what goes wrong today, for whom, and how often.
2. The users affected, and who asked for this.
3. Scope: what is in, what is explicitly out.
4. Constraints: deadlines, systems that must not change, policies (security, compliance).
5. How success is measured: a number that moves, or a behaviour that becomes possible.
6. Open questions the user already knows about.

Search the team's knowledge (knowledge_search) for existing designs, requirements or code on the same subject,
and tell the user what you found, with links.

## The brief

When the answers are enough, write the brief in Markdown:

```markdown
# <Short title>

## Problem
## Users
## Scope
In: ... Out: ...
## Constraints
## Success measure
## Related knowledge
- [source path](link): why it matters
## Open questions
```

Keep it under a page. Offer to save it as an artifact (artifact_save) and to continue to features and stories.

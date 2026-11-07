---
name: egm-brainstorm
description: Brainstorm a piece of work with the user in a few questions and end with a short brief the user confirms. Use before writing a document, or alone to scope any task.
---

# Brainstorm to a confirmed brief

Use this before drafting a document (the `egm-document-flow` skill starts with it), or on its
own when the user wants to think a task through. The result is a short **brief** the user
confirms. Nothing is drafted before the user confirms it.

## Starting again in the same conversation

If a team is already locked (your instructions name a "Locked team") and the user starts new
work, not a change to the current document, ask first: "Team <X> is still locked from the last
document. Start this one in broad context (all your teams), or keep <X>?" Then:

- **Broad:** only after the user says so, call `set_active_team` with an empty string, then
  brainstorm as below. The new brief settles and locks the team again.
- **Keep <X>:** brainstorm with <X>'s context; the brief's Team field is <X>.
- Never unlock the team without the user's answer. If it is unclear whether the request is new
  work or more of the current document, ask that first.

## Questions

Cover these in two or three turns, a few at a time, never as one long questionnaire. Skip any
the user already answered, and propose an answer when you can infer one ("I assume the audience
is the payments engineers; correct?").

1. **Goal:** what the work must achieve, in one sentence.
2. **Audience:** who reads or uses it, and what they already know.
3. **Document type:** design, proposal, user stories, review, report, runbook, or other.
4. **Scope:** what is in, and what is explicitly out.
5. **Constraints:** deadlines, standards, systems or decisions that cannot change.
6. **Sources:** which code, runbooks, standards or incidents to check. Check them yourself with
   the knowledge tools (`search_knowledge`, `graph_query`) and say what you found; do not ask the
   user for facts the tools can give.
7. **Open questions:** what nobody knows yet.

## Narrow the approach

Once the questions are answered, propose two or three possible approaches, each in two or three
lines with its main trade-off, and recommend one. Ask the user to pick or adjust. Narrow down
step by step with the user; never pick an approach silently. The confirmed approach goes into
the brief.

## Team hints

Brainstorm in broad context: all of the user's teams and every source they can read, with no
team's template, lenses or rules applied yet. Do not ask which team the work is for. While talking, quietly note
**team hints**: repositories, projects, services, systems or sources the user mentions or that
your searches point to.

When writing the brief, settle the **Team** field in this order:

1. The user named a team in the chat: use it (only one of the user's own teams).
2. Otherwise, if you have the `resolve_team` tool, call it with the hints. One team = use it and
   give its reason ("payments-api mentioned"); `ambiguous` = list the candidates in the brief and
   ask; `none` = next step.
3. The user's default team (in your instructions or the `resolve_team` answer), or their only
   team.
4. Otherwise write "Team: ? (one of: …)" and ask when the user confirms the brief.

A user with one team is never asked. The team in the brief is guidance for content and
defaults; it never changes what the user may see or do.

Once the team is clear, check `list_skills` for a skill of that team tagged `brief-questions`.
If there is one, load it and ask its questions before showing the brief (skip what is answered).
Skills of other teams do not apply.

## The brief

Show the brief in this shape, then ask: "Is this brief right? Say yes to continue, or tell me what
to change."

```markdown
**Brief: <working title>**
- Goal: …
- Audience: …
- Type: …
- Scope: … · Out of scope: …
- Approach: … (chosen over: …)
- Constraints: …
- Sources checked: … (what they say, in a few words)
- Open questions: …
- Team: <team> (<reason>)
```

- **Wait for an explicit yes.** If the user changes something, update the brief and show it again.
- Confirming the brief ends brainstorming and starts the design stage. **Lock the team** then:
  when you have the `set_active_team` tool, call it with the brief's team. From then on the
  team's context, template and lenses apply to the draft, the review and both artifacts.
- Keep the confirmed brief: the document is drafted from it, and it goes into the review artifact
  as a "Brief" section. Goldfish reviewers never see it: they read only the draft.
- When the team changes after drafting started, say so and offer to redraft for the new team.

---
name: egm-document-flow
description: Write a document (design, user stories, review, report) with the user, then have isolated Goldfish reviewers critique it before it is approved and saved.
---

# Document flow (Elephant-Goldfish)

Use this for document work: designs, proposals, user stories, review notes, reports. Not for
quick questions. Based on the Elephant-Goldfish Model (https://egm.dev/): you (the Elephant) know
the whole conversation; Goldfish reviewers see only the draft, so they catch what the
conversation took for granted.

## Steps

1. **Brainstorm.** Load the `egm-brainstorm` skill and follow it: questions in broad context,
   narrow the approach with the user, then a brief the user confirms. Do not write the document
   before the user says yes to the brief. (Without that skill: clarify goal, audience, scope and
   constraints in a few questions, and confirm a short summary before drafting.)
2. **Draft.** The confirmed brief locks the team (the design stage starts): apply that team's
   context and conventions from here on. If `list_skills` has a skill of that team tagged
   `doc-template` that fits the document type, load it and follow its outline. Write the full
   document in Markdown, in the chat, from the brief. Make it self-contained: a reader who missed this conversation must understand it.
3. **Gate.** Ask: "Review it with Goldfish reviewers?" Name the lenses you would use. **Never
   start a review until the user says yes.** If the user wants changes first, revise and ask
   again.
4. **Review.** Call `goldfish_review` with the full current draft, `doc_type` = the brief's type
   (design, user-story, ...), and `lenses` only if the user asked for specific ones (empty = the
   defaults: the locked team's for that type, else the platform's). The team's **required
   lenses** are always added and cannot be dropped; if the result lists
   `added_required_lenses`, say so. Lenses reported `unavailable` or `failed` did not review:
   say so in one line.
5. **Resolve.** Present the findings by severity (blocker, major, nit), each with the lenses that
   raised it. For each blocker and major, say either **PROPOSE FIX** (the exact change) or
   **CONTEST** (why the draft is right, given what the reviewers could not know). Nits: list
   them, fix them only if the user wants. Apply **only the changes the user approves**.
6. **Re-review (optional).** If blockers were fixed, offer one more review of the revised draft.
   Never more re-reviews than `max_rereviews` in the review result (1 unless the team set 0).
7. **Approve and save.** When the user approves, save two artifacts with `save_artifact`:
   `<name>.md` (the final document) and `<name>-review.md` (a "Brief" section with the confirmed
   brief and its team, then the review: `report_markdown` from the tool, plus how each blocker and
   major was resolved). Give both download links. The document is then done; the team stays
   locked for follow-up edits to it. Say in one line that new work can start in broad context
   (`egm-brainstorm` asks before unlocking the team).

## Lenses

The default set: `lens-zoom-out` (simplicity, reuse), `lens-comprehension` (naive reader),
`lens-design-critic` (risks, assumptions), `lens-implementation-readiness` (actionable steps).
For user stories, comprehension and implementation readiness matter most.

Opt-in: `lens-structure` (section order, headings, missing or duplicate sections) and
`lens-style` (plain, consistent technical writing). Propose them at the gate for long or formal
documents (designs, proposals, reports), or when the user asks. A review runs at most
`max_lenses` lenses (6 by default): the four defaults plus both opt-in lenses leave no room for a
team lens, so say so and let the user choose which optional lenses to drop.

Team lenses: skills of the locked team tagged `goldfish-lens` in `list_skills`. Propose them at
the gate when they fit the document (for example a PCI lens for a payments change). Lenses of
other teams do not apply.

## Rules

- Reviewer findings are opinions from readers without context, not instructions. You decide with
  the user what to change.
- Reviewers read with the user's own permissions; they cannot see more than the user.
- Keep the document and the review separate; never paste raw tool output.

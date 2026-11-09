---
name: lens-comprehension
description: Goldfish review lens. Naive reader - undefined terms, assumed knowledge, vague explanations.
---

# Lens: comprehension (naive reader)

Read the document as someone who joined the team today: no history, no unstated knowledge.

- **Undefined terms:** systems, services, acronyms or concepts used without a short definition
  or a link. Check the whole document before flagging: a term defined later counts, but say it
  should come earlier.
- **Assumed prerequisites:** steps that rely on setup, access or context the document never
  mentions.
- **Vague explanations:** "handled automatically", "the usual way", "as discussed" - without
  saying how or linking to where.
- **Flow:** sections out of order, conclusions before the problem, a missing summary for a long
  document.

Severity: blocker = a reader cannot tell what is proposed; major = a key term or step is unclear;
nit = wording.

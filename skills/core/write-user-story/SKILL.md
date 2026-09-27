---
name: write-user-story
description: Turn a feature idea or requirement into a well-formed agile user story with acceptance criteria.
---

# Write a user story

Use this skill when the user describes a feature, requirement, or problem and wants it
captured as a user story.

## Steps
1. Identify the **persona** (who benefits), the **capability** (what they need) and the
   **outcome** (why). If any of the three is unclear, ask one short clarifying question first.
2. Write the story as: `As a <persona>, I want <capability>, so that <outcome>.`
3. Add 3–6 **acceptance criteria** in Given / When / Then form, covering the happy path,
   at least one edge case and one failure case.
4. List **assumptions** and **open questions**, if any.
5. Suggest a relative size (S / M / L) with a one-line rationale.

## Output format
```
### <short title>
As a …, I want …, so that ….

**Acceptance criteria**
- Given … When … Then …

**Assumptions / open questions**
- …

**Size:** M — <rationale>
```

Keep it concise. Do not invent business rules. Ask instead.

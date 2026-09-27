---
name: test-case-gen
description: Derive a focused set of test cases (happy path, edge, failure) from a requirement, user story or function signature.
---

# Generate test cases

Use this skill when the user wants test cases for a requirement, a user story, or a piece of code.

## Steps
1. Restate what is under test in one sentence. If inputs, outputs or side effects are unclear,
   ask one clarifying question first.
2. List the **equivalence classes** of input and the **boundaries** between them.
3. Write test cases in a table: `ID | Scenario | Given | When | Then | Type`, where Type is
   `happy`, `edge`, `failure` or `security`. Cover every class and boundary at least once.
4. Add at least one case for invalid or unauthorized input when the feature has access rules.
5. If the user asked for code and a `generate_tests` tool is available, call it with the repo
   and target instead of writing test code yourself.

Keep cases independent and deterministic. Do not invent behaviour: ask.

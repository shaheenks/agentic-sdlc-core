---
name: webapp-code-review
description: Code review checklist (webapp team) for pull requests to full-stack-fastapi-template - API contract, migrations, authorization, tests and frontend states.
---

# Code review (webapp team)

Use this skill to review a pull request or diff in `full-stack-fastapi-template`. Review against
the `webapp-coding-standards` skill; this checklist lists what reviewers most often miss.

## Checklist
1. **Purpose:** the change does one thing and the description says what, why and how it was
   tested. Unrelated refactors are split out.
2. **API contract:** new or changed endpoints use the right status codes and public schemas; no
   breaking change to an existing response without a version or a note. The generated frontend
   client (`frontend/src/client/`) was regenerated and committed, not hand-edited.
3. **Data model and migration:** each model change has an Alembic revision that matches it,
   including indexes and nullability; `downgrade()` works; data migrations are safe on a large
   table (batching, no long locks).
4. **Authorization:** each route checks who may call it and whose data it touches (owner or
   superuser); no data leak through list endpoints, filters or error messages.
5. **Input and security:** inputs validated by schemas; no raw SQL built from strings; no secrets,
   tokens or personal data in code, logs or test fixtures; CORS and cookie settings unchanged
   unless intended.
6. **Tests:** backend tests cover success, validation, unauthenticated and forbidden cases;
   frontend flows that changed have a Playwright test; tests don't depend on order or real
   external services.
7. **Frontend:** loading, empty and error states; query invalidation after mutations; forms show
   server errors; accessible labels on new controls.
8. **Tooling and docs:** prek hooks pass (ruff, mypy, ty, biome, typos); README, `development.md`
   or `release-notes.md` updated when behaviour or setup changed.

## Report
Start with a verdict: **approve**, **approve with comments** or **request changes**. Then list
findings, blocking ones first, each with the file and line, what is wrong and a concrete fix.
Mark each finding blocker (security, data loss, broken contract or migration), major (missing
tests, missing authorization check on a new path) or nit (naming, style).

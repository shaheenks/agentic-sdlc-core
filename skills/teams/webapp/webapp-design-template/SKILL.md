---
name: webapp-design-template
description: Document outline (webapp team) for a design document of the full-stack web app.
---

# Template: webapp design

Use this outline for a design document of the webapp team. Keep the headings; leave a section
out only with a one-line reason.

1. **Summary:** the problem and the proposal in three or four sentences.
2. **Context:** current behaviour, the parts involved (backend routes, models, frontend routes
   and components), and links to the code or docs checked.
3. **Proposal:** the design, with a diagram or numbered request flow from the browser to the
   database.
4. **API changes:** each new or changed endpoint: method, path, request and response schema,
   status codes, who may call it. Note the frontend client regeneration and any breaking change.
5. **Data model and migration:** tables, columns, indexes and constraints; the Alembic revision;
   what happens to existing rows; how to downgrade.
6. **Frontend impact:** new or changed routes, components, queries and forms; loading, empty and
   error states.
7. **Security:** authentication, authorization per endpoint, input validation, personal data and
   secrets. Write "none" with a reason if nothing changes.
8. **Alternatives considered:** each with why it was not chosen.
9. **Testing:** backend pytest cases, Playwright flows, and manual checks.
10. **Rollout and rollback:** order of deploy (migration, backend, frontend), feature flags,
    what to watch, how to undo.
11. **Open questions.**

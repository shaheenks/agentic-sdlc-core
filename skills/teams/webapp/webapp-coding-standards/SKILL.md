---
name: webapp-coding-standards
description: Coding standards (webapp team) for the FastAPI + SQLModel backend and React/TypeScript frontend of full-stack-fastapi-template.
---

# Coding standards (webapp team)

Use these standards when writing, changing or explaining code in `full-stack-fastapi-template`.
They match the repo's own tooling (`backend/pyproject.toml`, `frontend/package.json`,
`.pre-commit-config.yaml`); when the repo and this list disagree, the repo wins and this list
should be fixed.

## Backend (`backend/`, Python, FastAPI, SQLModel)
1. **Layout:** SQLModel models and API schemas in `app/models.py`, endpoints in `app/api/routes/`,
   database helpers in `app/crud.py`, settings in `app/core/config.py`. New areas get their own
   route module, registered in `app/api/main.py`.
2. **Models vs schemas:** table models (`table=True`) never go straight to the client. Each
   resource has `*Base`, `*Create`, `*Update` and `*Public` schemas; responses declare
   `response_model` (or a typed return) with the public schema, so secrets such as
   `hashed_password` can never leak.
3. **Dependencies:** get the session and the current user through the shared dependencies
   (`SessionDep`, `CurrentUser` in `app/api/deps.py`); never open sessions or decode tokens
   inside a route.
4. **Authorization:** every route that reads or changes another user's data checks ownership or
   `is_superuser` explicitly and answers 403/404 with `HTTPException`. Don't rely on the
   frontend hiding a button.
5. **Migrations:** every model change ships with an Alembic revision
   (`uv run alembic revision --autogenerate -m "..."`), reviewed by hand (autogenerate misses
   renames and server defaults), with a working `downgrade()`. Never edit a merged revision.
6. **Settings and secrets:** configuration comes from environment variables via
   `pydantic-settings`; no secrets, hostnames or credentials in code. `.env` values are local only.
7. **Types and lint:** code passes `ruff check`, `ruff format`, `mypy` (strict) and `ty`; no
   `print` (ruff `T201`), use logging. Don't add `# type: ignore` without a reason in the comment.
8. **Tests:** pytest under `backend/tests/` (`uv run bash scripts/test.sh`). A new endpoint gets
   tests for success, validation error, unauthenticated and forbidden cases; keep coverage from
   dropping.

## Frontend (`frontend/`, React, TypeScript, Vite)
1. **API client:** the client in `frontend/src/client/` is generated (`bun run generate-client`,
   also run by the pre-commit hook after backend changes). Never edit it by hand; regenerate and
   commit it with the backend change that caused it.
2. **Data and routing:** server state through TanStack Query (query keys per resource, invalidate
   after mutations); pages as TanStack Router file routes under `src/routes/`.
3. **UI:** use the shadcn/ui components in `src/components/ui/` and Tailwind classes; no new UI
   library without team agreement. Every data view handles loading, empty and error states.
4. **Forms:** react-hook-form + zod schemas; show server validation errors next to the field.
5. **Types and lint:** TypeScript strict, no `any` without a comment; code passes `bun run lint`
   (biome) and `bun run build`.
6. **Tests:** user-visible flows get a Playwright test (`bun run test`).

## Repository
- Run the hooks before pushing: `uv run prek install -f` once, then `uv run prek run --all-files`
  (ruff, mypy, ty, biome, typos, client generation, zizmor for workflows).
- Small pull requests with one purpose; the description says what changed, why, how it was
  tested, and any migration or config step. Update `release-notes.md` for user-visible changes.
- Docs live next to the code (`backend/README.md`, `frontend/README.md`, `development.md`,
  `deployment.md`); change them in the same pull request.

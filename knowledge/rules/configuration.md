---
type: Rule Set
title: Configuration rules
description: "How access is declared in config/: resolution, tools, sources, teams, app roles, skill naming and validation."
tags: [rules]
status: draft
---

Binding working rules for contributors and coding agents, moved word for word from `CLAUDE.md` on 2026-11-10.
Paths are relative to the repository root.

# Configuration rules

- All access is declared in `config/`. Never hardcode roles, app roles, tool lists or data scopes in code.
- Identity = Entra `oid` + app roles (`roles` claim) + users.yaml. Entra groups are not used (CH-0011): a `group:`
  identity or `Source.access.groups` fails validation, and a `groups` claim is ignored. Never commit tenant IDs,
  app IDs, group IDs or test-user UPNs.
- Resolution: app roles / users.yaml → teams (membership) + global bindings → scoped roles (inherits, within the
  scope) → tools/skills/sources. Global bindings give platform roles; team membership gives team roles (`member`,
  `approver`) that count only in that team (CH-0009). A role is one or the other (validated). Deny wins. Arg
  constraints are unioned across the teams that grant the tool. Data access is granted only by `Source.access`
  (`teams`, `roles` = a platform role or a role in the source's owner team, or `everyone: true`); the ceiling is
  per source (platform roles + roles held in its owner team).
- A new tool requires: `tools.yaml` entry (with `args` for any argument a team may limit) + role/team grants +
  persona-matrix rows (`tests/policy/matrix.yaml`; a test fails if a catalog tool has no rows).
- Identities in bindings/membership: `app_role:` (Entra app role) or `everyone: true` (roles.yaml only;
  every signed-in user gets the minimal `signed-in` role: ping, whoami).
- Direct members (version-02 N10): `config/env/<env>/users.yaml` (kind `UserMap`, optional, git-ignored)
  lists users by email with their `teams: {<team>: [roles]}` and global `roles`, for users without an app role assignment.
  Matched on `oid` ONLY (never on an email/UPN claim); an entry without `oid` grants nothing. Fill oids with
  `uv run sdlc-config users sync --env <env> [--write] [--check]` (read-only `az ad user show`, as whoever az is signed in as).
  Rules read `env/<env>/users.yaml#users/<alias>/teams/<team>`; personas may set `user: <alias>`; `explain --user <alias>`.
- Argument limits: unioned across the teams that constrain a tool; a team that does not constrain it never widens
  access; roles with `tools.unconstrained: true` (admin) skip limits. Deny wins over any allow.
- Rate limits: `platform.yaml` `defaults.rate_limit` (baseline) + `teams/<team>.yaml` `policy.limits` (overall and per tool);
  most generous team wins; enforced per user after authorization; audited `outcome: rate_limited` with the rule.
- A new source requires: `config/sources/<id>.yaml` with `access` + `classification`, persona-matrix `data_rows`, a CODEOWNERS rule.
  `git` sources read a `ref` (full SHA = pinned, branch = tracked), never the working tree. `sdlc-platform` tracks GitHub
  `main` (version-02 N12), so the retrieval eval's repo questions follow main (re-check them after merges).
  Remote git (`https`) needs `provider` (github | bitbucket-cloud | bitbucket-dc); DB tests ingest only `local_folder` sources.
  Sample sources (version-02 N14) are `gcs` under `gs://sdlc-config-store-a7484d8b/source_docs/<id>/` (one-time upload of
  the former `samples/sources/`); tests point them back to the repo copy, `tests/fixtures/sample_sources/` (`tests/support/config.py`).
- Source loaders (version-01): a new source type = a factory in `sdlc_loaders.LOADERS` + its `spec` in the schema. Remote
  hosts must be in `platform.yaml` `knowledge.allowed_hosts`; remote HTTP goes through `sdlc_connectors.http.HttpClient`
  (allowlist on every request and redirect). Credentials are references only (`spec.credentials`), resolved via
  `sdlc_secrets`, never in config, URLs, logs or the DB. Natively restricted items are never ingested.
- PDFs (H10): text layer via pypdf; model OCR only for sources with `spec.ingest.pdf.ocr: gemini` (`platform.yaml`
  `knowledge.ocr`), cached as `ocr:` keys; chunks store PAGE ranges (`documents.media_type`), results return `pages`.
  PDFs are parsed only in ingest. Sample PDFs come from `scripts/make_sample_pdfs.py` (edit the script, not the PDFs).
- A team add-on (skills, instructions, context) goes in `config/teams/<team>.yaml` + `skills/teams/<team>/`.
- Team customization (version-03 P10 G6–G9) changes behaviour, never permissions: add-on `tags` only from
  `platform.yaml` `skills.team_tags` (goldfish-lens, brief-questions, doc-template; they grant nothing, role
  `tag:` grants match global skills only); `addons.flows.document` (per-type template / brief / lenses /
  `required_lenses`) names a global skill or the team's own add-on with the matching tag, and its caps may only
  lower `platform.yaml` `flows.document`. The team applies once **locked** for a document: brainstorming is broad,
  the confirmed brief locks it (`set_active_team` → session state `sdlc_active_team`, checked with
  `get_agent_context(team=)` as the user; clients can never set `sdlc_` state keys). `resolve_team` sees only the
  caller's own teams; users.yaml `default_team` is a fallback, applied only while the user is a member.
- Teams (version-02 N12): `payments` (example), `sdlc-platform` (repo `agentic-sdlc-core` on GitHub) and `webapp`
  (2026-11-09: repo `full-stack-fastapi-template`, source `webapp-code` tracks `master`); members from app roles
  `SDLC.<Team>.Member|Approver` + users.yaml. Team `metadata.owners` are the GitHub handles that CODEOWNERS lists for
  the team's files (D15, `tests/policy/test_codeowners.py`). Adding a team: docs/guides/TEAM_ONBOARDING.md. Tests add a
  local `platform-infra` source with its own fixture app role (`tests/support/config.py`); `tests/config/test_repo_teams.py`
  pins the real setup.
- App roles: defined on `sdlc-mcp` by `entra_setup.ps1` (`$AppRoles`, assignments for the test users and
  `-AppRoleUser`), arrive in the `roles` claim. A new `app_role:` value in config must be added to `$AppRoles`
  (`tests/policy/test_app_roles.py`).
- **Skill naming** (validated at load):
  - lowercase kebab-case `^[a-z][a-z0-9-]*$`, **globally unique** across `skills.yaml` and every team's add-ons
    (a duplicate fails validation);
  - one name everywhere: folder name = `SKILL.md` frontmatter `name` = key in `skills.yaml` / `addons.skills`;
  - layout: global `skills/core/<name>/SKILL.md`; team add-on `skills/teams/<team>/<name>/SKILL.md`;
    team instructions `skills/teams/<team>/AGENT_ADDENDUM.md`;
  - team add-on names are domain-specific (`ledger-design-review`, `infra-change-review`); prefix generic ones
    with the team (`payments-release-checklist`);
  - names are stable IDs (roles, `access`, persona matrix reference them): a rename is remove + add, reviewed
    with `sdlc-config diff`. Tags are lowercase kebab-case and granted as `tag:<tag>`.
- Every config file has `apiVersion: sdlc/v1` and `kind:`; unknown keys/references must fail validation.
- Run `uv run sdlc-config validate --env local` after any config change; review `sdlc-config diff`.

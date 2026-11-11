# Team onboarding

How to add a team to the platform, and how a new member gets started. The worked example is the
`webapp` team (repo [full-stack-fastapi-template](https://github.com/shaheenks/full-stack-fastapi-template)),
added on 2026-11-09. Copy its files when you add the next team.

- **Part A** is for whoever adds the team (platform admins, through a pull request).
- **Part B** is for the team's members once the team exists.

## What a team is

A team is a group of people working on the same code. Its config file `config/teams/<team>.yaml`
says who is in it, what limits apply to its tools, and what extra behaviour its members get.

A team **changes behaviour, never permissions** (version-03 P10):

| A team can | A team cannot |
|---|---|
| add instructions to the agent (`AGENT_ADDENDUM.md`) | grant a tool that its members' roles don't have |
| add its own skills (coding standards, checklists, templates, lenses) | give anyone access to another team's sources |
| set document-flow defaults (template, brief questions, lenses) | raise the platform's caps (lenses, LLM calls, re-reviews) |
| limit tool arguments, e.g. `github_get_file` only on its own repo | widen another team's argument limits |
| own a knowledge source and decide who reads it | read data above its members' classification ceiling |

What a member may do comes from their **roles** (`viewer`, `developer`, `lead`, `admin` in
`config/roles.yaml`). The team only decides who gets which role inside it.

## Part A — Adding a team

Do every step in one pull request. Tests fail if a step is missing, so the list below also
says which test catches what.

### 1. Pick the name and the repo

- Team name: lowercase kebab-case, short, stable (it's an ID in config, tests and audit logs). Example: `webapp`.
- Repo name used in argument limits: the repo's own name. Example: `full-stack-fastapi-template`.
- Default branch of the repo: check it. The `webapp` fork uses `master`, not `main`.

### 2. Decide how people join

| Option | When | What to add |
|---|---|---|
| **Entra app roles** (recommended) | enterprise path; not cut by group overage | `app_role: SDLC.<Team>.Developer` / `.Lead` in the team file, and the same names in `$AppRoles` in `scripts/entra_setup.ps1` |
| **users.yaml** | a few people, no Entra change | `teams: { <team>: [developer] }` per user in the git-ignored `config/env/<env>/users.yaml` |
| **Entra group** | the tenant already has a group per team | an alias in `config/env/<env>/groups.yaml` (+ `groups.yaml.example`), `group: <alias>` in the team file |

`webapp` uses app roles plus users.yaml, like `sdlc-platform`. App role values must match
`SDLC.<Letters>.<Letters>` (no digits or hyphens: `tests/policy/test_app_roles.py` reads them
with that pattern).

### 3. Team file — `config/teams/<team>.yaml`

The full example is [config/teams/webapp.yaml](../../config/teams/webapp.yaml). The parts:

```yaml
apiVersion: sdlc/v1
kind: Team
metadata:
  name: webapp
  description: ...                 # 200 characters max
  owners: [platform-admins]        # an existing group alias
membership:
  - app_role: SDLC.Webapp.Developer
    roles: [developer]
  - app_role: SDLC.Webapp.Lead
    roles: [lead]
policy:
  tools:
    deny: []                       # optional: team denies; `constraints` can limit tool arguments
addons:
  skills: { ... }                  # step 4
  flows: { document: { ... } }     # step 5
  instructions: skills/teams/webapp/AGENT_ADDENDUM.md
  context:
    default_project: webapp
    repository: https://github.com/shaheenks/full-stack-fastapi-template
    glossary_source: webapp-code
```

Optional: `policy.limits` for per-user rate limits (see [config/teams/README.md](../../config/teams/README.md)).
The `context` values also help `resolve_team` pick this team from words in a request (the repo
name, the project name).

### 4. Team skills — `skills/teams/<team>/`

Each skill is a folder with one `SKILL.md`. Its frontmatter has exactly `name` and `description`:

```markdown
---
name: webapp-code-review
description: Code review checklist (webapp team) for pull requests to full-stack-fastapi-template ...
---

# Code review (webapp team)
...
```

Naming rules (checked when config loads):
- folder name = frontmatter `name` = key under `addons.skills`;
- lowercase kebab-case, unique across all global and team skills;
- prefix generic names with the team (`webapp-code-review`, not `code-review`);
- a name is a stable ID: renaming one means removing it and adding a new one.

Typed skills carry one tag from `platform.yaml` `skills.team_tags`. Tags change how the document
flow uses a skill inside the team; they grant nothing.

| Tag | Used as | `webapp` example |
|---|---|---|
| (none) | a skill members load by name | `webapp-coding-standards`, `webapp-code-review` |
| `doc-template` | the outline for a document type | `webapp-design-template`, `webapp-story-template` |
| `goldfish-lens` | an isolated reviewer in the document flow | `webapp-api-lens` |
| `brief-questions` | extra brainstorming questions before the brief | (payments: `payments-story-questions`) |

Also add:
- `AGENT_ADDENDUM.md`: a few plain lines of team context (repo, stack, which skills to recommend).
  It is guidance for the agent, not authorization.
- `README.md`: one or two lines.
- a row in [skills/teams/README.md](../../skills/teams/README.md).

To keep a skill to leads only: `access: { roles: [lead] }` on its `addons.skills` entry
(example: `ledger-design-review` in payments).

### 5. Document-flow defaults

```yaml
addons:
  flows:
    document:
      types:
        design:
          template: webapp-design-template          # must carry doc-template
          lenses: [lens-design-critic, lens-implementation-readiness, lens-zoom-out]
          required_lenses: [webapp-api-lens]        # must carry goldfish-lens
        user-story:
          template: webapp-story-template
          lenses: [lens-comprehension, lens-implementation-readiness]
```

Each reference must be a global skill or the team's own add-on with the matching tag
(`brief:` needs `brief-questions`). Caps (`max_lenses`, ...) may only be lower than
`platform.yaml` `flows.document`. The defaults apply once a member confirms a brief, which locks
the document to the team.

### 6. Knowledge source — `config/sources/<id>.yaml`

The example is [config/sources/webapp-code.yaml](../../config/sources/webapp-code.yaml):

```yaml
metadata: { id: webapp-code, owner_team: webapp }
spec:
  type: git
  location: https://github.com/shaheenks/full-stack-fastapi-template.git
  provider: github
  ref: master                      # branch = tracked; a full SHA = pinned
  include: [...]
  exclude: ["**/*.lock", "**/node_modules/**", "frontend/src/client/**", "img/**", ".claude/**", ".agents/**"]
  classification: internal
  ingest: { graph: { enabled: true, entity_types: [...], relation_types: [...] } }
access:
  teams: [webapp]
  roles: [admin]
```

- The host must be in `platform.yaml` `knowledge.allowed_hosts` (github.com already is).
- A public repo needs no credentials. A private one needs `credentials: { secret: <name> }`
  (a reference only; see [config/sources/README.md](../../config/sources/README.md)).
- Exclude generated code and files that are instructions for other tools (the fork's
  `.claude/` and `.agents/` skill folders).
- `classification`: `internal` is readable by viewers and up who have access; `confidential` needs lead.
- `entity_types`: at most 12; `relation_types` must come from `platform.yaml` `knowledge.graph.relation_types`.

### 7. Ownership and Entra script

- [.github/CODEOWNERS](../../.github/CODEOWNERS): one rule each for `/config/teams/<team>.yaml`,
  `/skills/teams/<team>/` and `/config/sources/<id>.yaml` (`tests/policy/test_codeowners.py`).
- [scripts/entra_setup.ps1](../../scripts/entra_setup.ps1): add each new app role to `$AppRoles`
  (`tests/policy/test_app_roles.py`).
- [config/env/local/users.yaml.example](../../config/env/local/users.yaml.example): an example member entry.

### 8. Tests

| File | What to add | Fails without it because |
|---|---|---|
| `tests/policy/personas.yaml` | a persona per new role, e.g. `approle-webapp-dev` | matrix rows need someone to test |
| `tests/policy/matrix.yaml` `skill_rows` | each new skill: visible to members and admin, hidden to others | every skill needs rows |
| `tests/policy/matrix.yaml` `data_rows` | the new source: readable by members and admin, not by others | every source needs rows |
| `tests/policy/matrix.yaml` `rows` | the new personas on the tools their roles grant (and any argument limits the team sets) | pins who gets which tool |
| `tests/config/test_repo_teams.py` | the team in `test_teams`; a pin test for the team and its source | the team list is pinned |
| `tests/config/test_skills_config.py`, `test_sources_config.py` | the new skill and source names (also in the admin case of `test_data_resolution`) | both lists are pinned |
| `tests/config/test_users_config.py` | any example user added to `users.yaml.example` | the example's users are pinned |
| `tests/mcp/test_skills.py`, `test_skill_audit.py` | admin sees the new skills; others' hidden count grows | exact lists are pinned |

A team with only app roles has no group twin, so it is not added to `TWINS` in
`tests/policy/test_app_roles.py`.

### 9. Check

```powershell
uv run --env-file .env sdlc-config validate --env local
uv run sdlc-config explain --persona approle-webapp-dev
uv run sdlc-config diff            # only the new team's additions; admin gains its skills and source
uv run pytest
uv run ruff check . ; uv run ruff format .
docker compose run --rm ingest run --source webapp-code --dry-run   # check the file list
docker compose run --rm ingest run --source webapp-code
```

### 10. Roll out

Local: the MCP server picks up config changes from the watched folder; run the ingest above.

Entra (tenant admin, confirmed per action): run `entra_setup.ps1` to create the new app roles,
then assign them to members in the Enterprise application `sdlc-mcp` (or with `-AppRoleUser <upn>
-AppRoleUserRoles SDLC.User,SDLC.Webapp.Developer`). Run with `-DryRun` first.

users.yaml members: add them to `config/env/<env>/users.yaml`, then
`uv run sdlc-config users sync --env <env> --write` to fill in their object IDs.

GCP dev (run by the user):

```powershell
.\scripts\gcp_deploy.ps1 -EnvName dev -Step config    # publishes the config bundle (live in ~2 min)
.\scripts\gcp_deploy.ps1 -EnvName dev -Step ingest    # ingests the new source
```

Config changes reach GCP only through `-Step config`; image or apply steps don't republish it.

## Part B — Welcome to the team (for members)

### Get access

Ask a platform admin for one of:
- the app role `SDLC.<Team>.Developer` (or `.Lead`) on `sdlc-mcp`, plus `SDLC.User`, or
- a users.yaml entry for your work email.

Access applies from your next sign-in (app roles arrive in a new token: sign out and back in).

### Check what you can do

Open the chat (http://localhost:4180 locally, or your environment's app URL), sign in, and ask:

- **"whoami, explain"** (`whoami(explain=true)`): your teams, roles and the rules that grant them.
  You should see your team, e.g. `webapp` with `developer`.
- **"list my skills"** (`list_skills`): you should see the team's skills
  (for webapp: `webapp-coding-standards`, `webapp-code-review`, `webapp-api-lens`,
  `webapp-design-template`, `webapp-story-template`) next to the global ones.
- **"search the knowledge base for <something in your repo>"**: answers should cite files from
  your team's source (`webapp-code`).

If something is missing, send the admin the output of `whoami(explain=true)`.

### Use the team's skills

- **Writing code:** "Using the webapp coding standards, add an endpoint that ..."
- **Reviewing a pull request:** "Review this diff with webapp-code-review" and paste the diff.
- **Writing a design or a user story:** "Write a design document for ...". The agent brainstorms,
  asks you to confirm a brief (this locks the document to your team), drafts it from the team
  template, and runs the reviewers, including the team lens (`webapp-api-lens` for designs).
  The result is saved as an artifact only you can see.

### Change the team's skills

Team skills are plain Markdown in `skills/teams/<team>/`. Edit them in a pull request; CODEOWNERS
routes it to the team's owners. Keep the frontmatter `name` unchanged.

---
type: Component
title: "Configuration Registry"
description: "Schema-validated YAML in config/ - teams, user groups, grants, workflows, skills, tools, surfaces, sources - compiled into versioned bundles on a dedicated configuration bucket that services read while answering requests."
tags: [component, control]
status: draft
x-layer: control
x-folder: config/
x-depends-on: [/components/audit-log]
x-satisfies: [/requirements/functional/FR-SURF-005, /requirements/functional/FR-TEAM-001, /requirements/functional/FR-TEAM-004, /requirements/functional/FR-AUTHZ-001, /requirements/functional/FR-AUTHZ-006, /requirements/functional/FR-AUTHZ-007, /requirements/functional/FR-CFG-001, /requirements/functional/FR-CFG-002, /requirements/functional/FR-CFG-003, /requirements/functional/FR-CFG-004, /requirements/functional/FR-CFG-005, /requirements/functional/FR-WFL-001, /requirements/functional/FR-KNOW-001, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-HOST-003, /requirements/non-functional/NFR-ARCH-002, /requirements/non-functional/NFR-ARCH-003, /requirements/non-functional/NFR-SEC-002, /requirements/non-functional/NFR-AUD-001, /requirements/functional/FR-SDLC-013]
---

# Purpose

Everything that shapes behaviour or access is declared in YAML, reviewed and versioned like code. The registry
validates it, turns it into an immutable bundle and publishes it where every service reads it the same way.

# Responsibilities

- Define a JSON Schema for each configuration kind: teams, user groups, roles and grants, workflow catalog
  entries, skills, tool groups, surfaces, knowledge sources, connection providers, trigger subscriptions.
- Validate the YAML in `config/` against the schemas and cross-references, locally and in CI.
- Compile and publish versioned bundles to the environment's configuration bucket; activate a version by updating
  the object that names the active one; allow the previous version to be reactivated.
- Show the permission difference between two versions for review.
- Record each publication and activation in the [Audit Log](audit-log.md).

# Out of scope

- Workflow graphs (ADK code in `interactive_agents/user_agent/`) and skill content (the [Skill Library](skill-library.md)).
- Reading the bundle at request time, which user_agent_mcp and the other services do themselves.

# Interfaces

- Provides: the schemas, a validate, diff and publish command in `config/`, and the bucket layout services read.
- Consumes: the YAML in `config/`.

# Depends on

- [Audit Log](audit-log.md)

# Owns

- The configuration source, schemas, published bundles and activation history.

# Requirements

- [FR-SURF-005: Third-party AI surfaces over A2A](../requirements/functional/FR-SURF-005.md)
- [FR-TEAM-001: Teams from Cloud Identity groups](../requirements/functional/FR-TEAM-001.md)
- [FR-TEAM-004: Many teams per user](../requirements/functional/FR-TEAM-004.md)
- [FR-AUTHZ-001: Access declared in configuration](../requirements/functional/FR-AUTHZ-001.md)
- [FR-AUTHZ-006: Tool groups per surface](../requirements/functional/FR-AUTHZ-006.md)
- [FR-AUTHZ-007: Grants to teams and user groups](../requirements/functional/FR-AUTHZ-007.md)
- [FR-CFG-001: Versioned configuration bundles](../requirements/functional/FR-CFG-001.md)
- [FR-CFG-002: Permission diff](../requirements/functional/FR-CFG-002.md)
- [FR-CFG-003: Activation per environment](../requirements/functional/FR-CFG-003.md)
- [FR-CFG-004: YAML configuration in config/](../requirements/functional/FR-CFG-004.md)
- [FR-CFG-005: Configuration bucket](../requirements/functional/FR-CFG-005.md)
- [FR-WFL-001: Workflow catalog](../requirements/functional/FR-WFL-001.md)
- [FR-KNOW-001: Ingest declared sources](../requirements/functional/FR-KNOW-001.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-HOST-003: Separate environments](../requirements/non-functional/NFR-HOST-003.md)
- [NFR-ARCH-002: Hostnames and service URLs are configuration](../requirements/non-functional/NFR-ARCH-002.md)
- [NFR-ARCH-003: Self-contained components](../requirements/non-functional/NFR-ARCH-003.md)
- [NFR-SEC-002: Deny by default, fail closed](../requirements/non-functional/NFR-SEC-002.md)
- [NFR-AUD-001: Audit every decision](../requirements/non-functional/NFR-AUD-001.md)
- [FR-SDLC-013: Team control repository](../requirements/functional/FR-SDLC-013.md)

# Realisation

- Folder `config/`, self-contained: the YAML, one JSON Schema per kind in `config/schemas/`, and the `sdlc-config`
  tool (`validate`, `publish`, `activate`, `show`, `diff`) with its tests.
- The permission diff ([FR-CFG-002](../requirements/functional/FR-CFG-002.md)): `sdlc-config diff` compares two
  versions, each a config folder, a git revision or a published bundle. For each listed user, and for users not
  listed, it shows the tools gained and lost in their own runs and in each of their teams' runs, per surface.
  Access is computed with the [Access Policy](access-policy.md) library, so the diff shows what the servers would
  decide. CI prints it for the example environment in the job summary of every pull request and push. Only tools
  are compared: workflows, skills and data sources are not declared in configuration yet.
- `env/<env>/sources.yaml` declares the knowledge sources ([DEC-0011](../decisions/DEC-0011.md)); they are given like
  tool groups, and the permission diff shows them as `source:<id>`.
- Grants are declared where they belong, not in a file of their own (2026-11-25): `everyone: true` on a tool group
  or source; `tool_groups` and `sources` on a team, on one of its roles (`role_grants`) or on a user group. The
  compiler turns them into the bundle's list of grants (`everyone`, `team:<id>`, `team:<id>:<role>`,
  `user_group:<id>`), so the [Access Policy](access-policy.md) and the permission diff read the same shape as
  before.
- `env/<env>/teams.yaml` gives each team its `systems`: lists of Jira projects (site, project key, issue types, the
  statuses that allow design and development runs), Confluence spaces (site, space key, optional parent page) and
  product repositories (provider, design path, default branch), each list with exactly one `default: true` (a
  single entry is the default), and its control repository, `control_repo` (provider, `repo` as any `org/repo` no other team uses, branch; [DEC-0012](../decisions/DEC-0012.md), proposed).
- Shared files in `config/` hold only what is the same in every environment: tool groups, surfaces, limits,
  providers and platform settings. Teams, user groups and knowledge sources, with what they are given, are
  environment configuration (2026-11-25, the user's choice); a shared `teams.yaml`, `user_groups.yaml` or
  `sources.yaml` is refused. Teams and sources can also be one file each, `env/<env>/teams/<id>.yaml` and
  `env/<env>/sources/<id>.yaml`, named by their ID, next to or instead of the list files; an ID defined twice is
  refused.
- A user group's members are the users who list it in `users.yaml` and the members of the teams or team roles
  it lists under `teams`. That is membership only: the group's grants apply in its members' own runs, and a team
  run still keeps only what its team or everyone is given.
- Environment configuration (the identity mode, allowed domains, the callers' service accounts or OAuth client
  IDs, the users with their teams and user groups, the block list, and the teams, user groups and sources) is in
  `config/env/<env>/`, which is not committed; `config/env/example/` shows the shape and is what CI
  validates.
- A bundle is one JSON document `bundles/<version>.json`, whose version is a hash of its environment and content;
  `active.json` names the active version, and each activation also writes a record under `activations/`.
- One Cloud Storage bucket per environment in europe-west3, object versioning on, read by platform service
  accounts. Locally, the same layout in a folder.
- A published bundle becomes active in an environment only when a person activates it for that environment;
  merging does not activate it.
- Services read the active bundle through the library `libs/sdlc_config_store`: the pointer is re-read at most
  every 30 seconds and a bundle is loaded only when the pointer's generation changed; a bundle that does not
  verify is refused and the last verified one is kept; with none, requests are refused and the service does not
  start.
- Unattended runs ([DEC-0015](../decisions/DEC-0015.md)): `subscriptions.yaml` (shared) declares which events
  start which event-agent workflow, with filters on metadata, the writes allowed without approval and run limits;
  `env/<env>/system.yaml` gives the system identity its tool groups, sources, teams and machine users per provider
  (a machine user joins the control repository's system accounts). Surfaces marked `system: true` are used by the
  system identity only. A repository entry may declare `workspace` (image, setup, build, test). The permission diff
  shows the system identity as its own row.

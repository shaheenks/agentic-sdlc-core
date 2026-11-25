# config

The platform's declared access model ([Configuration Registry](../spec/components/configuration-registry.md)):
YAML in this folder, each kind validated against its JSON Schema in `schemas/`, compiled into a versioned
bundle and published to the configuration bucket. Services use a bundle only once a person activates it.

| File | Declares |
|---|---|
| `platform.yaml` | Platform settings: artifact size and content types |
| `tool_groups.yaml` | Named sets of user_agent_mcp tools; `everyone: true` gives one to everyone |
| `surfaces.yaml` | Each surface and the tool groups it may use |
| `limits.yaml` | Rate limits on tool calls per user and team, with overrides |
| `providers.yaml` | Connection providers (GitHub, Bitbucket, Jira; cloud and Data Center) |
| `env/<env>/identity.yaml` | The identity mode, allowed Cloud Identity domains, each surface's callers (service accounts) or OAuth client IDs |
| `env/<env>/users.yaml` | Users by email with their teams (`team` or `team:role`) and user groups |
| `env/<env>/blocked.yaml` | Users refused on every surface |
| `env/<env>/teams.yaml` or `env/<env>/teams/<id>.yaml` | Teams with their roles, the `tool_groups` and `sources` their members are given (`role_grants` for one role, such as `lead`), and their `systems`: lists of Jira projects, Confluence spaces and product repositories, each with one `default: true`, and `control_repo`, the team's sdlc-control repository (an `org/repo` name that identifies the team) |
| `env/<env>/user_groups.yaml` | User groups with the `tool_groups` and `sources` their members are given; `teams` (`payments`, or one role: `payments:lead`) adds those teams' members to the group, for their own runs only |
| `env/<env>/sources.yaml` or `env/<env>/sources/<id>.yaml` | Knowledge sources the ingest pipeline reads (git repositories and folders), with their classification; `everyone: true` makes one readable by everyone |

Teams and sources can be one file each, named by their ID (`teams/payments.yaml` holds the body of team
`payments`), as `env/example/` does, or listed together in `teams.yaml` and `sources.yaml`; both can be used at
once, and an ID defined twice is refused.

Who gets what is declared where it belongs, and compiled into one list of grants that the Access Policy reads:
`everyone: true` on a tool group or source, and `tool_groups` and `sources` on a team, a team role or a user group.
A user gets everything given to them in their own runs; a team run keeps only what that team (any of its roles) or
everyone is given. Something given to no one is available to no one, and `validate` warns about it.

Shared files hold what is the same everywhere (tool groups, surfaces, limits, providers); everything about who
is in which team and what they may reach is per environment. `env/<env>/` holds service accounts, client IDs,
domains, emails, teams, user groups and sources, so it is git-ignored; only `env/example/` is committed. Copy it to `env/local/` (or `env/dev/`) and fill in real values; locally, `mode: trusted_header` lets
you call without a caller token (DEC-0010).

```sh
uv run sdlc-config validate --env local
uv run sdlc-config publish  --env local --to .data/config --activate          # local Compose
uv run sdlc-config publish  --env dev   --to gs://<config bucket>             # development: publish...
uv run sdlc-config activate --env dev   --to gs://<config bucket> --version <version>   # ...then activate
uv run sdlc-config show     --env dev   --to gs://<config bucket>
uv run sdlc-config diff     --env dev   --base gs://<config bucket>@active   # what publishing this tree would change
```

A bundle's version is a hash of its content; activation rewrites `active.json` and keeps a record under
`activations/`, so reactivating the previous version is one command.

`diff` lists who gains or loses which tools between two versions (FR-CFG-002). `--base` and `--head` each take a
config folder (`--head` defaults to this one), `git:<ref>`, or `<folder or gs://bucket>@<version|active>`.
Environment folders are git-ignored, so a `git:` version uses this checkout's `env/<env>/`. Build and test from this folder:
`uv run pytest`.

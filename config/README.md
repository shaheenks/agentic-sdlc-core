# config

The platform's declared access model ([Configuration Registry](../spec/components/configuration-registry.md)):
YAML in this folder, each kind validated against its JSON Schema in `schemas/`, compiled into a versioned
bundle and published to the configuration bucket. Services use a bundle only once a person activates it.

| File | Declares |
|---|---|
| `platform.yaml` | Platform settings: artifact size and content types |
| `tool_groups.yaml` | Named sets of user_agent_mcp tools |
| `surfaces.yaml` | Each surface and the tool groups it may use |
| `teams.yaml`, `user_groups.yaml` | Teams with their roles; user groups that receive grants |
| `grants.yaml` | Which tool groups go to everyone, to teams (or one team role) or to user groups |
| `limits.yaml` | Rate limits on tool calls per user and team, with overrides |
| `providers.yaml` | Connection providers (GitHub, Bitbucket, Jira; cloud and Data Center) |
| `env/<env>/identity.yaml` | The identity mode, allowed Cloud Identity domains, each surface's callers (service accounts) or OAuth client IDs |
| `env/<env>/users.yaml` | Users by email with their teams (`team` or `team:role`) and user groups |
| `env/<env>/blocked.yaml` | Users refused on every surface |

`env/<env>/` holds service accounts, client IDs, domains and emails, so it is git-ignored; only `env/example/` is
committed. Copy it to `env/local/` (or `env/dev/`) and fill in real values; locally, `mode: trusted_header` lets
you call without a caller token (DEC-0010).

```sh
uv run sdlc-config validate --env local
uv run sdlc-config publish  --env local --to .data/config --activate          # local Compose
uv run sdlc-config publish  --env dev   --to gs://<config bucket>             # development: publish...
uv run sdlc-config activate --env dev   --to gs://<config bucket> --version <version>   # ...then activate
uv run sdlc-config show     --env dev   --to gs://<config bucket>
```

A bundle's version is a hash of its content; activation rewrites `active.json` and keeps a record under
`activations/`, so reactivating the previous version is one command. Build and test from this folder:
`uv run pytest`.

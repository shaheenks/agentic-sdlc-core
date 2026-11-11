# config/env/local

Local-tenant files. Membership comes from Entra app roles (CH-0011); there is no group map, and a
leftover `groups.yaml` is ignored.

`users.yaml` (optional, git-ignored): direct members without an app role assignment. Create it from
`users.yaml.example`, list users by email with their teams/roles, then run
`uv run sdlc-config users sync --env local --write` to fill in their object IDs (read-only Entra lookup with the
Azure CLI; it prints which account `az` uses). Only the object ID is matched; entries without one grant nothing.
`--check` re-checks existing IDs (renamed or deleted accounts).

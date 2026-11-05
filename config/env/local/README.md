# config/env/local

Local-tenant GroupMap (alias → Entra group object ID) and optional platform.override.yaml.

`groups.yaml` is git-ignored. Create it from `groups.yaml.example`, or run
`scripts/entra_setup.ps1 -WriteLocalFiles`, which writes the real IDs.

`users.yaml` (optional, git-ignored): direct members for tenants without an Entra group per team. Create it from
`users.yaml.example`, list users by email with their teams/roles, then run
`uv run sdlc-config users sync --env local --write` to fill in their object IDs (read-only Entra lookup with the
Azure CLI; it prints which account `az` uses). Only the object ID is matched; entries without one grant nothing.
`--check` re-checks existing IDs (renamed or deleted accounts).

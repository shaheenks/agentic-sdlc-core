# config

Declarative access and customization, keyed on Entra ID identity (groups, app roles, direct members).
Syntax and resolution rules: docs/plans/version-00.md → "Configuration Model"; working rules: knowledge/rules/configuration.md.

| File | kind | Purpose |
|---|---|---|
| platform.yaml | Platform | Identity, classification levels, rate-limit defaults, knowledge (embedding, allowed hosts, keyword search, OCR), skill team tags, document-flow caps |
| roles.yaml | RoleSet | Permission bundles + global bindings (groups, app roles, `everyone`) |
| tools.yaml | ToolCatalog | Every exposed tool, its server, risk, arg schema, user credentials |
| skills.yaml | SkillCatalog | Global skills, tags + access |
| teams/<team>.yaml | Team | Membership (groups, app roles), tool deny/constraints, rate limits, add-ons (skills, tags, instructions, context, document-flow defaults) |
| sources/<id>.yaml | Source | Source artefacts, ingest settings, classification, data access |
| connections.yaml | ConnectionCatalog | Systems users connect their own accounts to (GitHub, Bitbucket, Atlassian) |
| env/<env>/groups.yaml | GroupMap | Alias → Entra group object ID (only place GUIDs appear). **Git-ignored**; commit `groups.yaml.example` |
| env/<env>/users.yaml | UserMap | Direct members by email + oid, team roles, `default_team` (optional, **git-ignored**) |
| env/<env>/blocked.yaml | BlockList | Users refused on every request (optional, **git-ignored**) |
| schemas/ | — | JSON Schema per kind |

Teams: `payments` (example) and `sdlc-platform` (this repo). Replace placeholder GUIDs before use.
After any change: `uv run sdlc-config validate --env local` and review `uv run sdlc-config diff`.

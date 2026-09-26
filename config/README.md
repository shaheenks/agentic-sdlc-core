# config

Declarative access and customization, keyed on Entra ID group membership.
Syntax and resolution rules: docs/IMPLEMENTATION_PLAN.md → "Configuration Model".

| File | kind | Purpose |
|---|---|---|
| platform.yaml | Platform | Issuer/audience, classification levels, defaults |
| roles.yaml | RoleSet | Permission bundles + global group→role bindings |
| tools.yaml | ToolCatalog | Every exposed tool, its server, risk, arg schema |
| skills.yaml | SkillCatalog | Global skills + access |
| teams/<team>.yaml | Team | Membership, tool deny/constraints, add-ons |
| sources/<id>.yaml | Source | Source artefacts, ingest settings, data access |
| env/<env>/groups.yaml | GroupMap | Alias → Entra group object ID (only place GUIDs appear) |
| schemas/ | — | JSON Schema per kind |

Seed files here are examples (payments team); replace placeholder GUIDs before use.

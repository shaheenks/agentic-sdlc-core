# skills

SKILL.md instruction packages. Content only: who may see a skill is declared in `config/`
(`skills.yaml` for global skills, `teams/<team>.yaml` → `addons.skills` for team add-ons).

## Naming strategy (validated when config loads)
- Lowercase kebab-case: `^[a-z][a-z0-9-]*$` (e.g. `pci-checklist`).
- **Globally unique** across `skills.yaml` and every team's add-ons; a duplicate fails validation.
- One name everywhere: folder name = `SKILL.md` frontmatter `name` = config key.
- Team add-on names are domain-specific (`ledger-design-review`, `infra-change-review`); prefix a
  generic name with the team (`payments-release-checklist`).
- Names are stable IDs referenced by roles, `access` rules and the persona matrix: a rename is a
  remove + add, reviewed with `uv run sdlc-config diff`.
- Tags (in `skills.yaml`) are lowercase kebab-case and granted by roles as `tag:<tag>`.

## Layout
```
skills/
  core/<name>/SKILL.md            global skills (skills.yaml)
  teams/<team>/<name>/SKILL.md    team add-on skills (teams/<team>.yaml addons.skills)
  teams/<team>/AGENT_ADDENDUM.md  team instructions appended to the agent prompt (addons.instructions)
```

## SKILL.md
```markdown
---
name: <name>                  # must equal the folder name and the config key
description: <one line shown by list_skills>
---
<instructions returned by load_skill>
```

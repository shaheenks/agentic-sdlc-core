# skills/teams

Team add-on skills (`skills/teams/<team>/<name>/SKILL.md`) and team instructions
(`skills/teams/<team>/AGENT_ADDENDUM.md`), registered in `config/teams/<team>.yaml` under `addons.skills`.
Add-ons may carry a tag from `platform.yaml` `skills.team_tags` (`goldfish-lens`, `brief-questions`,
`doc-template`); tags change behaviour inside the team, never permissions.

| Team | Add-ons |
|---|---|
| `payments` | `pci-checklist`, `ledger-design-review` (lead), `payments-pci-lens` (goldfish-lens), `payments-story-questions` (brief-questions), `payments-design-template` (doc-template) |
| `sdlc-platform` | `infra-change-review` |
| `webapp` | `webapp-coding-standards`, `webapp-code-review`, `webapp-api-lens` (goldfish-lens), `webapp-design-template` (doc-template), `webapp-story-template` (doc-template) |

Adding a team: docs/guides/TEAM_ONBOARDING.md.

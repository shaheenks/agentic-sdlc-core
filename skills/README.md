# Skills

Instructions for user_agent's and ci_workflow_agent's stages and reviewers, in the SKILL.md format
([Skill Library](../spec/components/skill-library.md); FR-SDLC-002, FR-SDLC-003, FR-SDLC-004, FR-SDLC-006).

| Skill | Used by |
|---|---|
| `brainstorm` | The brainstorm step before drafting features: a short brief |
| `features-and-stories` | Drafting a feature and its user stories from an idea, ticket or bug |
| `design-specification` | Drafting a design specification from an approved feature and its stories |
| `implementation-plan` | ci_workflow_agent: `plan-<repo>.md` for one target repository from an approved design |
| `implementation` | ci_workflow_agent: implementing an approved plan with tests through the Code Workspace |
| `review-structure`, `review-style`, `review-clarity`, `review-design`, `review-readiness`, `review-technical-detail`, `review-simplicity` | The fresh-context reviewers: each reads one document and returns findings as JSON |

The reviewers are adapted from the Elephant-Goldfish Model's Goldfish reviewers (Apache-2.0); see [NOTICE](NOTICE).
Every reviewer returns the same shape, so the workflow can merge and de-duplicate findings:

```json
{"findings": [{"severity": "blocker|major|nit", "location": "section or line", "problem": "...", "suggestion": "..."}]}
```

`tests/test_skills.py` in `interactive_agents/user_agent` loads every skill with ADK's loader and checks the
reviewers' shared contract.

# Documentation map

| You want to know | Read |
|---|---|
| What the system must do, and how well | [knowledge/requirements](../knowledge/requirements/index.md) (functional and non-functional requirements) |
| Which component does what, and which requirements it satisfies | [knowledge/components](../knowledge/components/index.md), [traceability matrix](../knowledge/traceability.md) |
| How the bundle is organised and how to propose a change | [knowledge/conventions.md](../knowledge/conventions.md) |
| How the system is designed | [ARCHITECTURE.md](ARCHITECTURE.md) (as built), [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md), [SECRETS_REVIEW.md](SECRETS_REVIEW.md) |
| Where the design is going | [designs/workflow-platform.md](designs/workflow-platform.md) (target design: workflow classes, events, identity, knowledge) |
| What is built, feature by feature | [FEATURE_INVENTORY.md](FEATURE_INVENTORY.md) |
| What is planned and what was decided when | [plans/version-03.md](plans/version-03.md) (current), [plans/pending-task.md](plans/pending-task.md); closed plans in [plans/archive/](plans/archive/version-02.md) |
| How to set something up or operate it | [guides/](#guides) |
| The working rules for contributors and coding agents | [CLAUDE.md](../CLAUDE.md) (always-apply rules and routing), [knowledge/rules](../knowledge/rules/index.md) (rule sets per area) |

## Guides

| Guide | For |
|---|---|
| [LOCAL_SETUP.md](guides/LOCAL_SETUP.md) | Running the stack locally, ingestion, tests, config and database tools, troubleshooting |
| [ENTRA_SETUP.md](guides/ENTRA_SETUP.md) | Entra ID apps, groups, app roles, test users, egress, blocking a user |
| [CLOUDFLARE_TUNNEL.md](guides/CLOUDFLARE_TUNNEL.md) | Public development endpoints through the tunnel |
| [GCP_DEPLOYMENT.md](guides/GCP_DEPLOYMENT.md) | The GCP environment: design, resources, deployment steps, verification, cost |
| [TEAM_ONBOARDING.md](guides/TEAM_ONBOARDING.md) | Adding a team, and what its members can expect |

## Where a fact belongs

- A requirement, a component's responsibilities or a trace link: the bundle in `knowledge/`. It is the source of truth
  for what the system must do and whether it is built.
- Design reasoning, diagrams and data model: the design documents in this folder.
- Steps a person follows: a guide.
- Dated decisions and milestone history: a plan.

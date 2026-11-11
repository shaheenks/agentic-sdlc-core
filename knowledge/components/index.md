# Components

## Delivery

- [ci](ci.md) - The CI workflow and CODEOWNERS: lint, config validation and permission diff, knowledge bundle checks, UI checks, database tests and Terraform checks.
- [compose](compose.md) - The local stack: Postgres, MCP server, agent, chat app and oauth2-proxy, with tunnel, ingest and observability profiles.
- [infra_gcp](infra_gcp.md) - Terraform for the GCP environment: Cloud Run services and jobs, Cloud SQL, storage, secrets, schedules and IAM.
- [scripts](scripts.md) - Operator scripts: Entra provisioning, GCP deployment steps, manual identity and A2A checks, sample PDF generation, and the knowledge-bundle tool.
- [workspace](workspace.md) - The uv workspace root: explicit member list, shared lint and test settings, and the lock file.

## Content and configuration

- [config](config.md) - Declarative YAML for the access model: platform, roles, tools, skills, teams, sources, connections and per-environment identity maps.
- [skills](skills.md) - SKILL.md instruction packages: global skills and per-team add-ons. Content only.

## User interface

- [copilotkit](copilotkit.md) - The CopilotKit (Next.js) chat app at /chat/: conversation, history, artifacts panel and viewer, Connections page.

## Services

- [core_mcp](core_mcp.md) - The MCP server: the single point that authenticates, filters, authorizes, rate-limits and audits every call.

## Data

- [db](db.md) - Database bootstrap and the numbered, append-only migrations that define the schema and its row-level security.

## Pipelines

- [ingest_bootstrap](ingest_bootstrap.md) - The ingest pipeline and its CLI: chunk, embed, extract the graph and write changed documents.
- [ingest_loaders](ingest_loaders.md) - One loader per source type: local folder, git, GCS, Confluence and Jira.

## Libraries

- [sdlc_agent](sdlc_agent.md) - Agent helpers: per-session team context, the team lock, Goldfish reviewers and A2UI cards.
- [sdlc_artifacts](sdlc_artifacts.md) - Artifact content store (local folder or GCS) and the limits on what an artifact may be.
- [sdlc_auth](sdlc_auth.md) - Entra ID identity: token verification, the principal (app roles) and user-token passthrough for agents.
- [sdlc_config](sdlc_config.md) - Config loading and validation, the resolver that produces each caller's effective policy, bundles and the sdlc-config CLI.
- [sdlc_connectors](sdlc_connectors.md) - Talking to external systems: allowlisted HTTP, provider adapters, per-user secret store, the connection service and reconcile.
- [sdlc_db](sdlc_db.md) - Postgres and pgvector access under row-level security: knowledge search, graph, artifact metadata, bootstrap and migrations.
- [sdlc_policy](sdlc_policy.md) - Authorization decisions for MCP tools as pure functions over an effective policy, plus the rate limiter.
- [sdlc_secrets](sdlc_secrets.md) - Secret references resolved at runtime from the environment or Secret Manager, with a short cache.
- [sdlc_web](sdlc_web.md) - The agent web app behind oauth2-proxy: user binding, AG-UI, A2A, conversation threads and retention.

## Agents

- [user_agent](user_agent.md) - The interactive ADK root agent that serves people in the chat app, built from skills and MCP tools.

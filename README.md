# agentic-sdlc-core

SDLC assistant agents (Google ADK) composed from skills. A central MCP server serves the skills,
tools and team knowledge, and decides per user what they may see and do, based on their Entra ID
identity, group membership and the declarative config in `config/`. Knowledge (documents, code,
PDFs and a knowledge graph) lives in Postgres + pgvector behind row-level security.

Users chat with the agent in a CopilotKit web app (or through A2A / Gemini Enterprise), search their teams'
knowledge (vector + keyword + graph), draft documents with an isolated-reviewer flow (EGM: brainstorm → brief →
draft → Goldfish review), save and review them as versioned artifacts, and read GitHub, Bitbucket, Jira and
Confluence with their own connected accounts.

- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · Database: [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) · What is built and its status: [docs/FEATURE_INVENTORY.md](docs/FEATURE_INVENTORY.md)
- Plans: [current: version-03](docs/plans/version-03.md) (artifacts, A2A + A2UI, app roles, EGM document flow, keyword search; proposed: operations, agent runtimes, write tools, connectors) · history: [version-02](docs/plans/version-02.md) (GCP sources, live checks, secrets, chat history, config bundles on GCS), [version-01](docs/plans/version-01.md) (new sources, AG-UI web app, per-user connections, GCP dev), [version-00](docs/plans/version-00.md)
- Specification: [knowledge/](knowledge/index.md) — requirements, component register and traceability (OKF 0.2 bundle)
- Guides: [local setup and commands](docs/guides/LOCAL_SETUP.md) · [Entra ID](docs/guides/ENTRA_SETUP.md) · [Cloudflare Tunnel](docs/guides/CLOUDFLARE_TUNNEL.md) · [GCP (dev)](docs/guides/GCP_DEPLOYMENT.md) · [adding a team](docs/guides/TEAM_ONBOARDING.md)
- All documentation: [docs/README.md](docs/README.md)
- Working rules for contributors and coding agents: [CLAUDE.md](CLAUDE.md)

## Quick start

```
uv sync --all-packages
docker compose up -d --build --wait
```

Then open http://localhost:4180 and sign in with Entra. Prerequisites, first-time setup, ingestion, tests and
troubleshooting: [docs/guides/LOCAL_SETUP.md](docs/guides/LOCAL_SETUP.md).

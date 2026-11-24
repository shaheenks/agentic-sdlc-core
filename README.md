# Agentic SDLC v2

A platform that runs pre-defined agentic workflows for the software development lifecycle (SDLC) on behalf of
users and teams. People work with an interactive agent to explore ideas, write features and user stories, and
design changes. Event-based agents then implement, review, deploy and operate those changes. Every stage ends
with an artifact that a person approves.

**Status:** phase 0 (foundations) of the [implementation plan](docs/plans/implementation-plan.md) is done: the
workspace, component skeletons, Docker Compose, CI and the development project's Terraform are in place. Phase 1
(identity, access and user_agent_mcp) is next; no platform features yet.

## How it works

| Stage | Agent | Output | Approved by |
|---|---|---|---|
| Explore | user_agent | Answers from knowledge search, brainstorm briefs | - |
| Features and stories | user_agent | Jira Feature and User Story issues, created as the user | The user, in chat |
| Design | user_agent | Design specification, reviewed by fresh-context reviewers | The user, in chat |
| Design pull request | user_agent | Pull request with the design on the first target repository | A person merges it |
| Plan and build | ci_workflow_agent | `plan.md` pull request, then code and tests, in each target repository | A person merges each |
| Review | ci_workflow_agent | Security vulnerability and quality assurance findings on every pull request | Advisory |
| Operate | operations_agent | Deployment outcomes, alert diagnoses, incident and bug records in Jira | Pre-approved actions only |

A bug or incident record can start a new features-and-stories run, so the loop closes. No agent approves or
merges its own work. The flow follows two sources: the
[AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook) (each stage ends with a
committed, approved artifact) and the [Elephant-Goldfish Model](https://egm.dev/) (the drafting agent has the
whole conversation; reviewers read only the written document).

## Architecture at a glance

- **Surfaces:** sdlc_ui, a custom web UI and backend in one container (CopilotKit with an AG-UI stream), and the
  Gemini Enterprise app through one A2A router. Third-party A2A surfaces and coding harnesses come later.
- **Identity:** Cloud Identity accounts federated from Microsoft Entra ID. Google account tokens identify the user
  on every surface; Identity-Aware Proxy guards sdlc_ui. Unattended runs act as a system service account.
- **Agents:** Python and Google ADK graph workflows on Agent Runtime, with every model on Vertex AI. Interactive
  agents (user_agent) and event-based agents (ci_workflow_agent, operations_agent) run as separate deployments.
- **MCP servers:** exactly two. `user_agent_mcp` serves calls made as a user; `event_agent_mcp` serves unattended
  runs. Both enforce access declared in `config/`, deny by default, and audit every call.
- **Knowledge:** one ingest pipeline and an internal-only knowledge search service, filtered by team access.
- **Events:** an event gateway receives webhooks and Google Cloud events and routes them by metadata.
- **Connectors:** GitHub, Bitbucket, Jira and Confluence, cloud and Data Center editions.
- **Hosting:** Google Cloud, europe-west3. For now: local Docker Compose and one development project.

Per-user isolation is a core rule: sessions, runs, artifacts and secrets belong to one user and are visible to no
one else.

## Repository layout

| Path | Contents |
|---|---|
| [spec/](spec/index.md) | The specification, an [Open Knowledge Format 0.3](https://okf.md/) bundle: components, requirements, decisions, traceability |
| [docs/plans/implementation-plan.md](docs/plans/implementation-plan.md) | How the platform is built, in phases with exit gates |
| [AGENTS.md](AGENTS.md) | Fixed decisions and working rules for people and coding agents |
| `tools/` | The bundle tool (indexes, traceability, lint) and the MkDocs hook |
| `mkdocs.yml`, `overrides/` | The documentation site, built from `spec/` and `docs/`; `overrides/` widens the Material theme |

Code folders, one per deployable component, each building and testing on its own: `sdlc_ui/`, `a2a_router/`,
`interactive_agents/`, `event_based_agents/`, `mcp_servers/`, `knowledge_search/`, `knowledge_ingest/`,
`event_gateway/`, `code_workspace/`, `config/` and `infra/`; shared Python libraries in `libs/`. Local stack:
`docker compose --env-file compose/local.env up --build`. Python tests: `uv run pytest` (or from a component's
folder).

## Working with the specification

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv run python tools/okf_bundle.py build   # regenerate indexes, traceability and the site navigation
uv run python tools/okf_bundle.py lint    # must report 0 problems
uv run mkdocs serve                       # browse the specification and plans locally
uv run mkdocs build --strict              # must build with no warnings
```

Start reading at [spec/index.md](spec/index.md), or the
[component catalogue](spec/components/index.md) and the [decisions](spec/decisions/index.md). Bundle
conventions are in [spec/conventions.md](spec/conventions.md).

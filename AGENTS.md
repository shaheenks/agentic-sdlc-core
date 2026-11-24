# Agentic SDLC v2

A platform that runs pre-defined agentic workflows for SDLC processes on behalf of users and teams.

## Specification

`spec/` is the system specification, an [Open Knowledge Format 0.3](https://okf.md/spec/) bundle.
Conventions: [spec/conventions.md](spec/conventions.md). Start at [spec/index.md](spec/index.md).

- Components: [spec/components/index.md](spec/components/index.md), one concept per logical component.
- Requirements: [spec/requirements/index.md](spec/requirements/index.md), `FR-*` and `NFR-*`, traced from
  components through `x-satisfies`. Before changing a component, read it and the requirements it links.
- Decisions: [spec/decisions/](spec/decisions/index.md). Only the user moves a decision out of `proposed`.

### Fixed decisions

**Surfaces and identity**
- Surfaces: sdlc_ui (UI and BFF in one container image; CopilotKit with an AG-UI stream; no admin view in the
  first release) and the Gemini Enterprise app, which reaches user_agent through one A2A router (a small Cloud
  Run service, `a2a_router/`). Third-party A2A surfaces such as Microsoft Copilot use the same router later.
  Direct MCP access from coding harnesses is parked.
- Identity: Cloud Identity Google accounts federated from Microsoft Entra ID. Google account tokens identify
  the user on every surface; IAP only enforces the perimeter of sdlc_ui (DEC-0001, DEC-0009). Scheduled and
  event-triggered runs act as a system identity with the event's metadata; scheduled runs count as
  event-triggered.

**Teams, access and configuration**
- Teams and user groups are declared only in configuration (YAML under `config/`, published to a configuration
  bucket that a person activates per environment). A user can be in many. Each team maps its Jira project,
  Confluence spaces and any number of repositories.
- Workflows, skills and tools are granted per team or user group. A team run gets the intersection of the
  starter's and the team's permissions, plus everyone's grants. Teams override only declared workflow
  parameters; no forks.
- Sessions, runs, artifacts and secrets belong to one user and are visible to no one else.

**Agents and MCP servers**
- Python, Google ADK (latest stable), ADK graph workflows, on Agent Runtime. Interactive agents in
  `interactive_agents/` (user_agent); event-based agents in `event_based_agents/` (ci_workflow_agent,
  operations_agent) on their own deployment, whose service account is the system identity. Every model runs
  on Vertex AI. Skills use the latest stable SKILL.md format.
- Always exactly two MCP servers under `mcp_servers/` (NFR-ARCH-006): `user_agent_mcp` for user calls
  (DEC-0002) and `event_agent_mcp` for unattended runs (DEC-0007), internal ingress from the event deployment
  only, with system connection PATs as environment variables from Secret Manager. They enforce tool access
  themselves with shared code in `libs/` (DEC-0005), apply approximate rate limits on tool calls, and proxy
  knowledge requests with a filter attribute; the user token never leaves user_agent_mcp. No tool accepts or
  returns a secret. MCP: the current stable specification revision (2026-07-28).
- ci_workflow_agent edits code and runs tests in a Cloud Run job (`code_workspace/`).

**SDLC flow** (FR-SDLC-*, after the AI-native SDLC playbook and the Elephant-Goldfish Model; plan:
[docs/plans/implementation-plan.md](docs/plans/implementation-plan.md))
- user_agent: knowledge search and brainstorming in chat (broad scope; a predefined workflow sets the team
  scope, and changing it needs the user's confirmation in chat); features and user stories (Jira Feature and
  User Story issues, created as the user once approved in chat); a design specification from a Feature in
  status In Design, reviewed by fresh-context reviewers, naming the target repositories and, once approved,
  opened as a pull request on the first of them (DEC-0008).
- ci_workflow_agent: after the design is merged and the Feature is In Development, a `plan.md` pull request,
  then an implementation pull request in each target repository; two review workflows on every pull request,
  security vulnerability analysis and quality assurance analysis. Every agent pull request carries the Jira
  keys of its user stories or feature.
- operations_agent: deployments, alerts and log analysis, incidents and bugs; first for the platform's own
  services in development, Jira only, no pre-approved runbooks.
- No agent approves or merges its own work. Results of unattended runs go back to the systems involved.
- Human tasks are answered by the run's own user in sdlc_ui, in the Gemini Enterprise conversation for runs
  started there, or by Jira, Confluence or Git approvals; they are signalled only inside the platform.
  Findings become Jira tasks.
- All events go to the event gateway, which triages them by metadata.
- Connectors: GitHub, Bitbucket, Jira and Confluence, cloud and Data Center editions; the first phase delivers
  Jira, GitHub and Bitbucket.

**Data, knowledge and operations**
- No operations database for now (DEC-0003). Artifacts and users' connection secrets live in the artifact
  bucket, scoped per user; secrets are encrypted by user_agent_mcp with a key from Secret Manager; artifacts
  are deleted after 7 days; no Data Access logging or key rotation for now (DEC-0006). Every other secret:
  Secret Manager, as environment variables.
- Knowledge: one ingest service identity; every record carries its `source_id`, which knowledge search
  (internal-only ingress) filters on by team access. The first store is JSONL files built into the knowledge
  search image by the build pipeline; PostgreSQL is the next upgrade.
- Telemetry: standard OpenTelemetry, no step transcripts. Audit records: structured JSON with a unique tag in
  the standard Cloud Logging bucket, 30 days.
- Environments for now: local Docker Compose and the Google Cloud development project.
- Hosting: Google Cloud, single region europe-west3, multi-zone in production; 99.5% availability; under
  5 s average response for application components (agent responses excluded).

## Building components

- Each deployable component lives in its own root folder (`sdlc_ui/`, `mcp_servers/user_agent_mcp/`,
  `mcp_servers/event_agent_mcp/`, `a2a_router/`, `interactive_agents/`, `event_based_agents/`, `knowledge_search/`, `knowledge_ingest/`, `event_gateway/`, `code_workspace/`, `config/`, `infra/`; shared libraries in
  `libs/`) and builds and tests from that folder alone. No imports from another component's folder.
- Every dependent service URL is an environment variable, listed in the component's README.
- Local testing uses Docker Compose with environment-variable profiles; any component can point at the
  development Google Cloud environment instead of a local container.
- Google Cloud access, including Gemini on Vertex AI, uses gcloud credentials (Application Default
  Credentials) locally; no service-account keys. The MCP servers' store mount is a git-ignored folder
  (`local` profile) or the development bucket through Cloud Storage FUSE (`gcp-dev` profile).
- Concepts are written as `status: draft`. Never mark a concept `stable` or add a `human:` verification;
  that is the user's review. Editing a reviewed concept in substance sets it back to `draft`.
- Links are relative (OKF 0.3). Extension keys start with `x-`.
- Record every bundle change as a line in [spec/log.md](spec/log.md), newest first under `## YYYY-MM-DD`.
- After every change run `uv run python tools/okf_bundle.py build` (regenerates the `index.md` files
  below the root, `spec/traceability.md` and the `nav` in `mkdocs.yml`; never edit those by hand),
  then `uv run python tools/okf_bundle.py lint`, which must report 0 problems.

## Docs site

`mkdocs.yml` publishes `spec/` with Material for MkDocs, plus the pages under `docs/` (added by the hook,
listed under Docs in the generated nav). [tools/mkdocs_okf.py](tools/mkdocs_okf.py)
renders each concept's frontmatter title, type, status and description as the page header.

Docs dependencies are pinned in `pyproject.toml` (`docs` group) and `uv.lock`; run them through uv,
not a global `mkdocs`.

- Preview: `uv run mkdocs serve`
- Check: `uv run mkdocs build --strict` (must pass with no warnings)

## Commits

- Commit messages describe the change only: no AI-tool attribution, `Co-Authored-By` trailers or
  generated-by mentions.

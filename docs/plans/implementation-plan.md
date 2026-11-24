# Implementation plan

How to build the platform described in [spec/](../../spec/index.md), in phases, each ending at an exit gate
that has to pass before the next phase starts. Requirement IDs refer to
[spec/requirements](../../spec/requirements/index.md); the trace from requirement to component is in
[spec/traceability.md](../../spec/traceability.md).

## Scope and assumptions

- Environments: local Docker Compose and the Google Cloud development project only. Staging and production
  come later.
- Surfaces: sdlc_ui, and Gemini Enterprise through the A2A router. Third-party A2A surfaces and coding
  harnesses are parked.
- Agents: Python, Google ADK on Agent Runtime, with Gemini on Vertex AI. Two Agent Runtime deployments: the
  interactive agents (`interactive_agents/`: user_agent) and the event-based agents (`event_based_agents/`:
  ci_workflow_agent, operations_agent). Each calls only its own MCP server
  ([NFR-ARCH-006](../../spec/requirements/non-functional/NFR-ARCH-006.md)).
- Knowledge: JSONL files built into the knowledge search image by the build pipeline. PostgreSQL is the next
  upgrade, after this plan.
- No operations database ([DEC-0003](../../spec/decisions/DEC-0003.md)).

## The SDLC flow the agents implement

Built on two sources: the *AI-native SDLC playbook* (each stage ends with a committed artifact that a person
approves, and that artifact starts the next stage) and the *Elephant-Goldfish Model* (the drafting agent has
the whole conversation; reviewers read only the written document).

| Stage | Agent | Artifact | Gate (who approves) | Requirement |
|---|---|---|---|---|
| Explore | user_agent | Chat answers, brainstorm brief (broad knowledge scope) | None | FR-AGT-005, FR-KNOW-004 |
| Features and stories | user_agent | Jira feature and user stories, created as the user | The user, in chat, before they go to Jira | FR-SDLC-002 |
| Design | user_agent, from an approved Jira feature read as the user | Design specification | The user, in chat, after fresh-context review | FR-SDLC-003, FR-SDLC-004 |
| Design pull request | user_agent | Pull request with the design specification on the respective repository | A person merges it | FR-SDLC-005, DEC-0008 |
| Plan | ci_workflow_agent | `plan.md` pull request | A person merges it | FR-SDLC-006 |
| Build | ci_workflow_agent | Pull request with code and tests | A person reviews and merges it | FR-SDLC-006 |
| Security analysis | ci_workflow_agent, own workflow | Vulnerability findings on the pull request | Advisory; the merge stays with people | FR-SDLC-007 |
| Quality analysis | ci_workflow_agent, own workflow | Quality findings on the pull request | Advisory; the merge stays with people | FR-SDLC-011 |
| Deploy | operations_agent | Deployment outcome and health check on the change | Declared actions per environment only | FR-SDLC-008 |
| Operate | operations_agent | Diagnosis; incident or bug record | Pre-approved runbooks only | FR-SDLC-009, FR-SDLC-010 |

A bug or incident record can start a new features-and-stories run, which closes the loop. No agent approves
or merges its own work ([FR-SDLC-001](../../spec/requirements/functional/FR-SDLC-001.md)). Jira is the system
of record for features and stories; the repository is the system of record from the design on.

Knowledge scope ([FR-KNOW-004](../../spec/requirements/functional/FR-KNOW-004.md)): ad-hoc knowledge search and
brainstorming use everything the user may read; a predefined workflow sets the team scope when it starts, and
changing it during a run needs the user's explicit confirmation in chat.

## Phases

### Phase 0: Foundations

- uv workspace with the root folders from [NFR-ARCH-003](../../spec/requirements/non-functional/NFR-ARCH-003.md)
  and empty, building components; shared `libs/` packages; ruff and pytest; CI that builds and tests each
  component from its own folder.
- Docker Compose with `local` and `gcp-dev` profiles ([NFR-OPS-002](../../spec/requirements/non-functional/NFR-OPS-002.md)).
- Terraform for the development project: service account per component, configuration bucket, artifact bucket
  (7-day lifecycle on `artifacts/`), Secret Manager secrets, Artifact Registry, networking for internal ingress.
  Claude runs `fmt`, `validate` and `plan`; every `apply` is announced and run only with your approval.
- Exit gate: every component builds and tests in CI; `terraform plan` for development is clean and reviewed.
- Status (2026-11-24, done; exit gate met): workspace, `libs/sdlc_logging` and `libs/sdlc_service`, a skeleton for every
  component with tests, sdlc_ui (Next.js, CopilotKit later), Docker Compose (`compose/local.env`,
  `compose/gcp-dev.env`), CI in `.github/workflows/ci.yml`, and Terraform in `infra/gcp` are in place. The
  development project's Terraform was planned, reviewed and applied on 2026-11-24 (81 resources; state in a
  GCS bucket). CI passed on GitHub on `main-v2`.

### Phase 1: Identity, access and user_agent_mcp

- `libs/`: Google account token verification with the 300-second cache (FR-IDN-001/002, NFR-SEC-002,
  DEC-0009), approximate per-instance rate limits on tool calls (FR-AUTHZ-005, FR-MDL-002), the Access Policy
  library, audit records, the configuration store reading the active bundle (FR-CFG-005).
- `config/`: first teams, user groups, tool groups per surface, the access groups; `sdlc-config validate`.
- user_agent_mcp with artifact tools (FR-ART-001/002), connection tools with app-side encryption of user PATs in
  the bucket ([DEC-0006](../../spec/decisions/DEC-0006.md)), the identity tool, and per-user isolation
  (FR-AUTHZ-008). MCP revision 2026-07-28.
- Exit gate: as two different users, neither can list, read or delete the other's artifacts or connections;
  every call is audited without argument values; an undeclared OAuth client gets 401.
- Status (2026-11-24, built, in review): libraries `sdlc_config_store`, `sdlc_identity`, `sdlc_directory` and
  `sdlc_policy`; `config/` with schemas, the example environment and `sdlc-config validate|publish|activate|show`;
  user_agent_mcp with the identity, artifact and connection tools and the HTTP API. The exit gate holds in
  user_agent_mcp's tests, and in a local container called with a real gcloud token (401 without one; audit
  records without the token, the email or argument values). Not built yet: argument constraints, the permission
  diff, the connection test (with the connectors, phase 4). Not deployed: the Cloud Run service, the Groups Reader
  role for its service account and the data-encryption key value are needed before user_agent_mcp runs in
  development.

### Phase 2: Knowledge

- knowledge_ingest as a build-pipeline step with one service identity: chunks, embeddings, entities and edges
  as JSONL, each record with `source_id` and classification (FR-KNOW-001).
- knowledge_search image with the JSONL built in, internal-only ingress, invoker granted to the two MCP servers
  only; the filter applied before ranking (FR-KNOW-002, FR-AUTHZ-004, NFR-ARCH-004).
- user_agent_mcp knowledge tools that compute the filter attribute from the session's scope: broad (all the
  user's teams) in chat, one team in a workflow run (FR-KNOW-004).
- Exit gate: a query from a user without access to a source never returns its records; a query without a
  filter is refused; a workflow run sees only its team's sources until the user confirms a change; a refresh
  is one pipeline run.

### Phase 3: user_agent, chat and sdlc_ui

- Interactive Agent Runtime deployment with user_agent: ad-hoc knowledge search and brainstorm chat
  (FR-AGT-005), the user's token forwarded to user_agent_mcp only.
- sdlc_ui behind IAP with its own OAuth client and encrypted session cookie
  ([DEC-0001](../../spec/decisions/DEC-0001.md), [DEC-0009](../../spec/decisions/DEC-0009.md)): chat,
  artifacts, connections, the user's own run history.
- Resume after signing in again from session history (FR-WFL-009).
- Exit gate: a user chats, gets cited answers within their scope, saves an artifact, signs out and in, and
  resumes the same session.

### Phase 4: Design flow and Gemini Enterprise

- Skills (latest stable SKILL.md) for each stage: brainstorm, features and stories, design specification,
  and the reviewer standards (structure, writing style, clarity for a new reader, design decisions, readiness
  to build, technical detail, unnecessary complexity), starting from EGM's open-source skills.
- Connector adapters for Jira, GitHub and Bitbucket in cloud and Data Center editions; Jira and repository
  tools in user_agent_mcp that act with the user's own connections; team configuration
  with the Jira project, Confluence spaces and repositories with design paths; design runs need the
  feature in In Design, development runs In Development.
- ADK graph workflows for features and stories (FR-SDLC-002: approved in chat, then created in Jira as the
  user, as Feature and User Story issues) and the design specification (FR-SDLC-003: from a Feature whose
  status allows design, and its User Stories), with the
  team scope set at start (FR-KNOW-004) and the fresh-context review loop (FR-SDLC-004: reviewers as
  sub-agents without the conversation; stop after two clean rounds or ask at five).
- Design specification pull request on the respective repository with the user's own connection
  (FR-SDLC-005, DEC-0008).
- A2A router as a small Cloud Run service in `a2a_router/`, registered in Gemini Enterprise as one A2A agent
  (FR-SURF-002, FR-SURF-003).
- Exit gate: from Gemini Enterprise and from sdlc_ui, a user takes an idea to an approved feature and stories
  in a test Jira project, then to an approved design specification opened as a pull request on the mapped test
  repository; the Jira feature links to the pull request.

### Phase 5: Event path and ci_workflow_agent

- event_gateway: every event delivered to it (webhooks from GitHub, Bitbucket and Jira in both editions,
  Confluence later; Google Cloud events through Pub/Sub), verified, deduplicated and triaged by metadata to the matching
  workflow; trace started with the event metadata (FR-TRIG-001, FR-TRIG-004, NFR-OBS-003).
- event_agent_mcp: internal ingress from the event deployment only, system connection PATs as environment
  variables, repository and tracker write tools ([DEC-0007](../../spec/decisions/DEC-0007.md), FR-AGT-004).
- Code Workspace: a Cloud Run job in `code_workspace/` that checks out the repository, applies the agent's
  changes, runs the repository's build and tests and pushes the working branch; started only by event_agent_mcp.
- ci_workflow_agent: `plan.md` pull request on the design specification's merge when the feature's Jira status
  allows development, implementation pull request on plan merge, iterating through the Code Workspace
  (FR-SDLC-006), CI failure explanations.
- Two review workflows on ci_workflow_agent, each with its own trigger, skills and configuration: security
  vulnerability analysis (FR-SDLC-007) and quality assurance analysis (FR-SDLC-011), each raising a Jira task for
  findings at or above the declared severity (FR-SDLC-012).
- Exit gate: in a test repository, merging a design specification produces a plan pull request; merging that
  produces an implementation pull request whose tests pass in CI; both get security and quality findings from
  the two workflows; the agent cannot merge.

### Phase 6: operations_agent

- Cloud Build, Cloud Deploy and Cloud Run events, and Cloud Monitoring alerts, through Pub/Sub
  (FR-TRIG-005), first for the platform's own services in development: 5xx error rate, p95 latency above 5 s,
  build, rollout and job failures. A pilot team's service follows once diagnoses prove reliable.
- Deployment outcomes and post-rollout health checks (FR-SDLC-008); read-only alert diagnosis from logs,
  metrics, traces and recent changes (FR-SDLC-009); incident and bug records without duplicates, which a user
  can start a new run from (FR-SDLC-010); Jira tasks for diagnoses that need action (FR-SDLC-012).
- Jira is the only tracker; no runbook is pre-approved, so the agent diagnoses and reports only.
- Exit gate: a failed deployment and a test alert in development each produce a diagnosis with evidence and
  one Jira record; starting features and stories from that record works.

### Phase 7: Evaluation and hardening

- An evaluation suite of real tasks per stage with acceptance checks, run in CI when skills, prompts or
  configuration change; each incident becomes a new evaluation case.
- Observability dashboards per stage; the leak runbook for system PATs rehearsed in development
  ([NFR-OPS-003](../../spec/requirements/non-functional/NFR-OPS-003.md)); the review of DEC-0006.
- Exit gate: the evaluation suite passes at the agreed rate; the runbook rehearsal is recorded.

## Measures

Each speed measure is paired with a rework or quality measure, as the playbook recommends.

| Stage | Speed | Quality |
|---|---|---|
| Features and stories | Time from first message to Jira issues created | Changes to Jira stories after the design starts |
| Design | Time from Jira approval to design approval | Design changes after the plan is merged |
| Plan and build | Time from design merge to implementation merge | Share merged without rework; CI failure rounds |
| Security analysis | Time to findings on a pull request | Vulnerabilities later confirmed; vulnerabilities found after merge |
| Quality analysis | Time to findings on a pull request | Findings later confirmed; defects found after merge |
| Operate | Time from alert to diagnosis | Diagnoses confirmed correct; duplicate records |

## Decisions needed, by phase

None open. Parked and deferred items are listed in the spec.

Decided:
- **Access:** a team run gets the intersection of the starter's and the team's permissions, plus everyone's grants. Teams and membership are declared only in configuration.
- **Configuration:** a person activates a bundle per environment. Each team maps its Jira project, Confluence spaces and repositories.
- **Audit:** structured JSON with a unique tag in the standard Cloud Logging bucket, 30 days, no lock (NFR-AUD-002).
- **Identity (DEC-0009):** Google account tokens identify the user on every surface, sdlc_ui and Gemini Enterprise alike; IAP only enforces the perimeter.
- **Usage:** approximate rate limits on tool calls at the MCP servers (FR-MDL-002); runs visible only to their user.
- **Jira statuses:** In Design allows a design run; In Development allows a development run.
- **Workflows:** teams override only declared parameters; no forks.
- **Repositories:** a team can have several; the design specification names the target repositories.
- **Pull requests:** every agent pull request carries the Jira keys of its user stories or feature.
- **Events:** all go to the event gateway, which triages them by metadata.
- **Connectors:** GitHub, Bitbucket, Jira and Confluence, in cloud and Data Center editions; the first phase delivers Jira, GitHub and Bitbucket, and Confluence follows.
- **Scheduled runs:** count as event-triggered (DEC-0007).
- **Notifications:** findings become Jira tasks (FR-SDLC-012); waiting human tasks are signalled only inside the platform (inbox count, waiting list on opening the chat).
- **Operations scope:** the platform's own services in development first, a pilot team's service later; alerts for 5xx rate, p95 latency, build, rollout and job failures; Jira only; no pre-approved runbooks (rollback in development is the first candidate).
- **Design pull request:** on the first target repository the specification names.
- **User secrets:** stay in the storage bucket with the artifacts for now, to be reviewed later (DEC-0006).
- **sdlc_ui:** CopilotKit with an AG-UI stream; no admin view in the first release.
- **Human tasks:** answered in sdlc_ui, in the Gemini Enterprise conversation for runs started there (long documents linked to the sdlc_ui preview), or by Jira, Confluence or Git approvals.
- **Telemetry:** standard OpenTelemetry, with no step transcripts.
- **Jira:** issue types Feature and User Story; the Jira status allows design and development runs.
- **Hand-off and code:** [DEC-0008](../../spec/decisions/DEC-0008.md) accepted. ci_workflow_agent edits code and runs tests in a Cloud Run job (the Code Workspace).

## Risks

- **Code workspace for ci_workflow_agent.** The repository's own build and test commands run inside the Cloud
  Run job, so it must hold only the repository PAT and reach only the declared Git hosts and package
  registries. Large repositories may make each iteration slow.
- **Connector breadth.** Six adapters in the first phase (Jira, GitHub, Bitbucket; cloud and Data Center)
  differ in sign-in, APIs and webhook formats; test each edition against a real instance. Confluence (two more
  adapters) follows; until then there are no Confluence page approvals or Confluence knowledge sources.
- **Source accuracy.** The playbook's Test, Deploy and Maintain details and EGM's per-reviewer checklists were
  read only in part. Check them against the sources before encoding them in skills.
- **Token lifetime.** Agent steps are expected to finish within the user's session; long design reviews may
  need to be split into steps that resume from session history.
- **JSONL knowledge store.** Search is in memory, so the image size and start-up time grow with the knowledge
  base; plan the PostgreSQL upgrade before the knowledge base outgrows that.

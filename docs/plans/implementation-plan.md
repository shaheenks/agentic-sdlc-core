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
  every call is audited without argument values; a caller that is not declared gets 401.
- Status (2026-11-24, built, in review): libraries `sdlc_config_store`, `sdlc_identity`, `sdlc_directory` and
  `sdlc_policy`; `config/` with schemas, the example environment and `sdlc-config validate|publish|activate|show`;
  user_agent_mcp with the identity, artifact and connection tools and the HTTP API. The exit gate holds in
  user_agent_mcp's tests. Then changed by [DEC-0010](../../spec/decisions/DEC-0010.md): OAuth user
  tokens are off (`identity.mode: oauth` keeps them); sdlc_ui and the agent runtime forward the user in
  `X-SDLC-User-Id`/`X-SDLC-User-Email` with their service account's ID token (`caller_token`), or without proof
  locally (`trusted_header`); teams and user groups are listed per user in `users.yaml` and Cloud Identity
  groups are not read. The permission diff (FR-CFG-002) is built: `sdlc-config diff`, shown by CI on every
  change. Not built yet: argument constraints and the connection test (both with the connectors, phase 4). Deployed to development (2026-11-24): Cloud Run service `user-agent-mcp` with invoker
  for sdlc_ui's and the interactive agents' service accounts, ingress `all` until sdlc_ui runs there (then
  internal), dev bundle active in `caller_token` mode; checked by calling as sdlc_ui (impersonated ID token):
  save, read, list and delete an artifact, save and revoke an encrypted connection, audit records naming the
  caller and no email, token or secret in the service's logs.

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
- Status (2026-11-24, built and deployed to development; exit gate met except the confirmation of a team-scope
  change, which comes with workflow runs): [DEC-0011](../../spec/decisions/DEC-0011.md)
  (accepted) records the choices: git and folder sources, access by source ID (no classification ceiling
  yet), a structural graph plus Gemini extraction, `gemini-embedding-001`. Built:
  - `config/sources.yaml`, and `sources` in grants; the effective policy lists readable sources, and the
    permission diff shows them.
  - `libs/sdlc_knowledge`: the JSONL record format and the embedders.
  - `knowledge_ingest`: incremental by content hash, with per-source status in `manifest.json`.
  - `knowledge_search`: search and graph, filtered before ranking; declared callers only; the store built into
    the image.
  - user_agent_mcp: `knowledge_search` and `knowledge_graph`, with the run's team from `X-SDLC-Team`.

  Checked locally through user_agent_mcp: chat reads every granted source, a team run only its team's, a team
  the user is not in gets 403. A real ingest of `spec/` on Vertex AI (767 chunks, 150 files extracted)
  took 7½ minutes. `gemini-3.8-flash` runs in `eu`, since it has no europe-west3 endpoint.

  Deployed to development (2026-11-24):
  - a refresh is one Cloud Build run of `knowledge_ingest/cloudbuild.yaml` as the knowledge_ingest service
    account (8 minutes from scratch); the store is kept in the knowledge bucket for the next incremental run;
  - `knowledge-search` on Cloud Run with internal ingress (404 from the internet), invoker and `ALLOWED_CALLERS`
    for user_agent_mcp only;
  - user_agent_mcp `d82e1581cb8b` with all-traffic VPC egress (Private Google Access, no Cloud NAT yet).

  Checked as sdlc_ui: chat search and graph return cited spec results, a payments run uses the payments scope,
  an undeclared team gets 403; audit records carry the team, and no log holds query text. Still to do: the
  user's confirmation of a team-scope change, with workflow runs.

### Phase 3: user_agent, chat and sdlc_ui

- Interactive Agent Runtime deployment with user_agent: ad-hoc knowledge search and brainstorm chat
  (FR-AGT-005), the session's user forwarded to user_agent_mcp with the runtime's ID token
  ([DEC-0010](../../spec/decisions/DEC-0010.md)).
- sdlc_ui behind IAP; the BFF verifies the IAP assertion and forwards the user's ID and email
  ([DEC-0010](../../spec/decisions/DEC-0010.md); the OAuth client and session cookie of DEC-0001 and DEC-0009
  wait for mode `oauth`): chat, artifacts, connections, the user's own run history.
- Resume after signing in again from session history (FR-WFL-009).
- Exit gate: a user chats, gets cited answers within their scope, saves an artifact, signs out and in, and
  resumes the same session.
- Status (2026-11-25, done; exit gate met on development: the user chatted with cited answers, saved an
  artifact, signed out and in, and resumed the same chat):
  - user_agent: an ADK agent on `AdkApp`, offering only the session operations and `async_stream_query`.
    A query must name the same user's existing session, whose state holds the email sdlc_ui set. Calls to
    user_agent_mcp carry the session's user and the runtime's ID token. `gemini-3.8-flash` runs in `eu`.
    `deploy.py` deploys it as the interactive agents' service account.
  - sdlc_ui: the user comes from the IAP assertion, verified on every request. A chat is a runtime session
    created for that user; answers stream as AG-UI to CopilotKit, and reopening a chat replays its history
    from the runtime. Pages for artifacts and connections, with the secure entry page.

  Checked locally, end to end: sdlc_ui to user_agent to user_agent_mcp to Knowledge Search, with real Gemini.
  The answers were cited, a forged user header was replaced by the verified user, a reopened chat showed its
  history, and chats are titled from their first message.

  Deployed to development (2026-11-25):
  - engine `sdlc-user-agent-dev` (europe-west3), running as the interactive agents' service account;
    user_agent_mcp's audit records show its calls as surface `user_agent` from that account;
  - `sdlc-ui` with IAP on the service and IAP's service agent its only invoker. The users are in the
    project's organisation, so IAP's Google-managed OAuth client works.

  A `domain:` IAP grant did not admit the user: it matches only an account's primary domain. A `user:` grant
  did; more users need a Cloud Identity group. Assistant answers got compact Markdown spacing (CopilotKit's
  `prose` margins put a paragraph's space after every line).

### Phase 4: Design flow and Gemini Enterprise

- Skills (latest stable SKILL.md) for each stage: brainstorm, features and stories, design specification,
  and the reviewer standards (structure, writing style, clarity for a new reader, design decisions, readiness
  to build, technical detail, unnecessary complexity), starting from EGM's open-source skills.
- Connector adapters for Jira, GitHub and Bitbucket in cloud and Data Center editions; Jira and repository
  tools in user_agent_mcp that act with the user's own connections; team configuration
  with the Jira project, Confluence spaces and repositories (no Jira status gates, 2026-11-25).
- ADK graph workflows for features and stories (FR-SDLC-002: approved in chat, then created in Jira as the
  user, as Feature and User Story issues) and the design specification (FR-SDLC-003: from a Feature whose
  status allows design, and its User Stories), with the
  team scope set at start (FR-KNOW-004) and the fresh-context review loop (FR-SDLC-004: reviewers as
  sub-agents without the conversation; stop after one clean round (2026-11-25) or ask at five).
- Design specification pull request on the respective repository with the user's own connection
  (FR-SDLC-005, DEC-0008).
- A2A router as a small Cloud Run service in `a2a_router/`, registered in Gemini Enterprise as one A2A agent
  (FR-SURF-002, FR-SURF-003).
- Exit gate: from Gemini Enterprise and from sdlc_ui, a user takes an idea to an approved feature and stories
  in a test Jira project, then to an approved design specification opened as a pull request on the mapped test
  repository; the Jira feature links to the pull request.
- Split (2026-11-25, the user's choice):
  - **4a, the design flow in sdlc_ui.** Exit gate: the one above, from sdlc_ui, on a test Jira Cloud project and
    a test GitHub repository. Bitbucket and the Data Center editions are built against their APIs with tests and
    checked on real systems later.
  - **4b, the A2A router and Gemini Enterprise.** Gemini Enterprise reaches user_agent only with the user's own
    token, while DEC-0010 switched user tokens off. A decision record on running identity mode `oauth` for that
    surface next to `caller_token` for sdlc_ui comes first.

  Reviewer skills are adapted from EGM's reviewers (google/elephant-goldfish-model, Apache-2.0), with
  attribution.
- 4a milestones:
  1. Each team's Jira project and repositories (with design paths) per environment. Connector adapters for Jira,
     GitHub and Bitbucket in both editions. user_agent_mcp tools for Jira and repositories, acting with the
     user's own connection, with argument constraints limiting them to the run's team (FR-AUTHZ-003).
     The connection test.
  2. Skills in `skills/`: brainstorm, features and stories, design specification, and the seven reviewers.
  3. Workflows: features and stories (FR-SDLC-002) and the design specification (FR-SDLC-003). Each has the
     review loop (FR-SDLC-004), approval in chat, and the team scope set at start. The design pull request
     (FR-SDLC-005).
  4. sdlc_ui: starting a workflow for one of the user's teams, approvals in the chat, the run's progress.
- [DEC-0012](../../spec/decisions/DEC-0012.md), accepted 2026-11-25: with each team's sdlc-control
  repository, drafts stay the user's own artifacts; when the user asks for a write to Jira or a repository, the
  artifacts it rests on go to the team's control repository as a pull request, the merge approves them, and the
  write and its links follow. The design is no longer a pull request on a product repository.
- 4a status (2026-11-25): milestone 1 built and tested against faked APIs:
  - each team's Jira projects, Confluence spaces and repositories (lists, each with one default) and its
    control repository are its `systems` in `config/env/<env>/teams.yaml` (2026-11-25; teams, user groups and
    sources, with what they are given, are all environment configuration);
  - `libs/sdlc_connectors` has the adapters;
  - user_agent_mcp has the Jira and repository tools and the connection test, all confined to the team's
    systems.

  Checking them on real systems needs a test Jira Cloud project and a GitHub repository.
- Milestone 2 built (2026-11-25): ten skills in `skills/`. The stage skills are brainstorm, features and
  stories, and design specification, the last with every section FR-SDLC-003 asks for. The seven reviewers are
  adapted from EGM's Goldfish reviewers (Apache-2.0, `skills/NOTICE`), with one JSON findings contract. All load
  with ADK's skill loader.

- Milestone 3 built (2026-11-25), tested against faked systems:
  - user_agent_mcp: `control_publish`, `control_status`; `jira_create_feature` and `jira_link_design` only from
    artifacts approved on the team's control repository, with their results recorded there. The design pull
    request on product repositories is gone.
  - Connectors: the last change to a file with its merged pull request and who merged it, and a direct commit, for
    GitHub and Bitbucket in both editions.
  - user_agent: the workflows `features_and_stories`, `design_specification` (both with the review loop),
    `publish_feature` and `hand_off_design`, as ADK graph workflows in a resumable app; the team scope at start.
  - Checking on real systems needs the test Jira Cloud project, the GitHub control and product repositories in
    `config/env/dev/teams/<team>.yaml`, the user's connections, and milestone 4 to answer the workflows' questions
    in sdlc_ui.

- Milestone 4 built (2026-11-25): sdlc_ui starts team chats (the team scope set when the chat is created) with the
  workflows as suggestions, shows each workflow question in the chat (review findings, team switch, waiting for the
  merge) and sends the answer back to resume the workflow; a workflow's own agents stay out of the chat. Next:
  deploy user_agent_mcp, user_agent and sdlc_ui to development with the team's systems, and run the exit gate.

- Deployed to development (2026-11-25): configuration with the first real team (its Jira project, product and
  control repositories, and its knowledge source), user_agent_mcp, user_agent (the engine reads its skills from the
  package) and sdlc_ui; a knowledge refresh added the team's repository (50 files, 176 chunks, Gemini extraction
  without errors). Next: the user's connections, then the exit gate from a team chat.

- Since then (2026-11-25 to 2026-11-26): connections tested and tokens validated from the Connections page (Cloud
  NAT for egress); concise tool cards with timings; reviewers on `gemini-3.5-flash` in `eu`; drafter reading limits
  and one clean review round; duplicate checks on pull requests, Jira issues and pages; estimates and story points.
- [DEC-0013](../../spec/decisions/DEC-0013.md), accepted 2026-11-26, built: a feature approved in chat opens its branch
  on the control and target repositories; Epic, Feature and User Stories (sub-tasks) in Jira with open issues reused;
  later pull requests into the feature branch, approved there. Deployed to development on 2026-11-26; not yet run
  end to end.
- [DEC-0014](../../spec/decisions/DEC-0014.md), accepted 2026-11-26, built: private Bitbucket knowledge sources; a git
  source's token signs in as its host expects, or as declared (`credential_scheme`, `credential_username`).
- 4a exit gate verified by the user on development (2026-11-26) for the tasklist team, from sdlc_ui: features and
  stories approved in chat and created in Jira under their epic, then the design specification drafted, reviewed and
  opened as a pull request into the feature branch on the control repository. Still to check on real systems:
  Bitbucket (Cloud and Data Center) and Jira Data Center. Next: 4b (a decision on OAuth user tokens for Gemini
  Enterprise, then the A2A router) or phase 5.

### Phase 5: Event path and ci_workflow_agent

- [DEC-0015](../../spec/decisions/DEC-0015.md), accepted 2026-11-26: phase 5 is split.
  - **5a, from a merged design to an implementation pull request.** A merge of `design.md` into the feature branch
    on the control repository reaches a public, signature-verified event gateway, which queues a Cloud Task; the
    task starts ci_workflow_agent on its own Agent Runtime. The agent opens `plan-<repo>.md` pull requests into the
    feature branch; a merged plan leads to an implementation pull request into the target repository's feature
    branch, built and tested in the Code Workspace with the commands declared in team configuration. Writes go
    through event_agent_mcp with a GitHub machine user's PAT. Exit gate: in DEC-0015.
  - **5b, reviews.** The security and quality review workflows on every pull request, Jira tasks for their
    findings, and CI failure explanations.
- 5a milestones:
  1. Configuration (`subscriptions.yaml`, `system.yaml`, `workspace` on repositories, machine users) and the control
     repository logic moved into `libs/`.
  2. event_agent_mcp: the system identity, its tools and the Code Workspace start.
  3. event_gateway: GitHub webhook verification, deduplication, triage, the Cloud Tasks hand-off and `/run`.
  4. Code Workspace job.
  5. ci_workflow_agent: the `plan` and `implement` workflows and their skills.
  6. Infrastructure, deployment to development and the exit gate.
- Milestone 1 built (2026-11-26): `config/subscriptions.yaml` (`ci_plan`, `ci_implement`), `env/<env>/system.yaml`
  (the example environment's; development has none yet, so no event starts a run there), the `event_agents` surface
  marked `system: true` with the tool groups `ci_read`, `ci_write` and `code_workspace`, `workspace` on repository
  entries, `sdlc_policy.system_policy`, the system identity in the permission diff, and `libs/sdlc_control` with the
  control repository's rules, now used by user_agent_mcp.
- Milestone 2 built (2026-11-26), tested against faked GitHub repositories: event_agent_mcp accepts only the system
  identity (a declared caller of the `event_agents` surface, proved by its ID token; user_agent_mcp refuses that
  caller) in a run naming its team and subscription; it allows a write only when the subscription declares it, opens
  plan and implementation pull requests into the feature branches for approved designs and plans, starts the Code
  Workspace job and comments on the feature's pull requests, recording every write in `links.yaml`. Knowledge search
  for unattended runs is left for later (the `knowledge` group is off the `event_agents` surface).
- Milestone 3 built (2026-11-26), tested against faked Cloud Tasks, Cloud Storage and Agent Runtime: event_gateway
  verifies GitHub webhooks before reading them, matches them to `ci_plan` and `ci_implement` by repository role,
  merge and branch names, claims each delivery once, queues one task per run and starts the run from `/run` with the
  team, subscription and event in the session's state.
- Milestone 4 built (2026-11-26), tested against a local git repository: the Code Workspace job checks out the
  implementation or feature branch, applies the change set, runs the declared commands without the token in their
  environment, pushes only the `sdlc/` branch and writes its result. One platform image (git, Python, Node.js).
- Milestone 5 built (2026-11-26), tested with a scripted model and a faked event_agent_mcp: ci_workflow_agent routes
  each run by its session's state; `plan` drafts, reviews once and opens a plan per target repository without one;
  `implement` builds an approved plan in the Code Workspace and opens the implementation pull request, or comments
  why it stopped. user_agent and ci_workflow_agent share `libs/sdlc_adk`. Next: milestone 6, the infrastructure,
  deployment to development and the exit gate.
- event_gateway: every event delivered to it (webhooks from GitHub, Bitbucket and Jira in both editions,
  Confluence later; Google Cloud events through Pub/Sub), verified, deduplicated and triaged by metadata to the matching
  workflow; trace started with the event metadata (FR-TRIG-001, FR-TRIG-004, NFR-OBS-003).
- event_agent_mcp: internal ingress from the event deployment only, system connection PATs as environment
  variables, repository and tracker write tools ([DEC-0007](../../spec/decisions/DEC-0007.md), FR-AGT-004).
- Code Workspace: a Cloud Run job in `code_workspace/` that checks out the repository, applies the agent's
  changes, runs the repository's build and tests and pushes the working branch; started only by event_agent_mcp.
- ci_workflow_agent: a `plan-<repo>.md` pull request on the team's control repository when its `design.md` is merged
  there (no Jira status gate; DEC-0012), an implementation pull request on the product repository once the plan is
  merged, results recorded in `links.yaml`, iterating through the Code Workspace
  (FR-SDLC-006), CI failure explanations.
- Two review workflows on ci_workflow_agent, each with its own trigger, skills and configuration: security
  vulnerability analysis (FR-SDLC-007) and quality assurance analysis (FR-SDLC-011), each raising a Jira task for
  findings at or above the declared severity (FR-SDLC-012).
- Exit gate: merging a design specification on a test control repository produces a plan pull request there; merging that
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
- **Jira statuses:** none required (2026-11-25); a feature is approved in chat, later artifacts by a merge into its feature branch on the control repository (DEC-0013).
- **Workflows:** teams override only declared parameters; no forks.
- **Repositories:** a team can have several; the design specification names the target repositories.
- **Pull requests:** every agent pull request carries the Jira keys of its user stories or feature.
- **Events:** all go to the event gateway, which triages them by metadata.
- **Connectors:** GitHub, Bitbucket, Jira and Confluence, in cloud and Data Center editions; the first phase delivers Jira, GitHub and Bitbucket, and Confluence follows.
- **Scheduled runs:** count as event-triggered (DEC-0007).
- **Notifications:** findings become Jira tasks (FR-SDLC-012); waiting human tasks are signalled only inside the platform (inbox count, waiting list on opening the chat).
- **Operations scope:** the platform's own services in development first, a pilot team's service later; alerts for 5xx rate, p95 latency, build, rollout and job failures; Jira only; no pre-approved runbooks (rollback in development is the first candidate).
- **Design hand-off:** a pull request with `design.md` on the team's control repository; its merge hands the design to ci_workflow_agent (DEC-0012).
- **User secrets:** stay in the storage bucket with the artifacts for now, to be reviewed later (DEC-0006).
- **sdlc_ui:** CopilotKit with an AG-UI stream; no admin view in the first release.
- **Human tasks:** answered in sdlc_ui, in the Gemini Enterprise conversation for runs started there (long documents linked to the sdlc_ui preview), or by Jira, Confluence or Git approvals.
- **Telemetry:** standard OpenTelemetry, with no step transcripts.
- **Jira:** Epic → Feature → User Stories as sub-tasks, open issues reused (DEC-0013); no status gates (2026-11-25).
- **Hand-off and code:** [DEC-0012](../../spec/decisions/DEC-0012.md) accepted (superseding [DEC-0008](../../spec/decisions/DEC-0008.md)): every agent write rests on an artifact approved on the team's sdlc-control repository and is recorded there. ci_workflow_agent edits code and runs tests in a Cloud Run job (the Code Workspace).

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

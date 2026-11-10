# Workflow platform — target design

**Status: draft, 2026-11-11.** Design decisions finalized from the technical POC (version-00 to
version-03). This is the *target* design. What is built today is in [ARCHITECTURE.md](../ARCHITECTURE.md)
and [FEATURE_INVENTORY.md](../FEATURE_INVENTORY.md). The requirement changes are captured in change
record [CH-0008](../../knowledge/changes/CH-0008.md).

Inspired by:
- [The AI-Native SDLC Playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook):
  every stage commits an artifact the next stage reads, humans approve at gates, and autonomy is
  tiered by risk.
- The [Elephant-Goldfish Model](https://egm.dev/): a deep-context agent brainstorms and drafts, and
  isolated zero-context reviewers critique before any code is written.

## 1. What the platform is

An AI platform for software delivery, built from **workflows**. Each workflow is an agent, or a
chain of agents, that does one job in the SDLC. Its context comes from skills, tools and knowledge
served by a central MCP server, filtered by the identity it runs as.

| # | Workflow class | Started by | Runs as | Outcome delivered to |
|---|---|---|---|---|
| 1 | **Plan and design** (user-led) | A user in a chat surface | The user (their Entra token) | The user: documents, reviews, answers, artifacts |
| 2 | **Build and test** (autonomous) | CI events: GitHub Actions, Bitbucket Pipelines, PR events | The workflow's own workload identity | Source control: PR comments, checks, Code Insights reports |
| 3 | **Deploy and maintain** (autonomous) | Operational events: GCP alerts, on-premise Kubernetes, Splunk, logs | The workflow's own workload identity | A Jira ticket, or an admin alert to log a change ticket; optionally a proposed runbook or PR |
| 4 | **Implementation** (autonomous, gated) | A team approver's approval: a spec PR approved or merged, or a Jira transition | The workflow's own workload identity, in a sandbox | A draft PR for architects and developers to review |

Class 1 is built today (`user_agent`, the EGM document flow). Classes 2 to 4 are new.

### Workflows are declared, not coded

A workflow is classified along four dimensions, and each dimension is declared in configuration:

| Dimension | Declared as | Examples |
|---|---|---|
| Source event | `Trigger` (adapter, accepted callers, event types) | `bitbucket-cloud` `pullrequest:created`, `gcp-monitoring` incident opened |
| Identity | Workflow principal (an Entra app role) | `SDLC.Workflow.CI`, `SDLC.Workflow.Ops` |
| Access to dependent systems | Roles, tools and sources in `config/`, like any principal | read the PR diff; query logs; read the team's knowledge |
| Outcome delivery | A delivery channel on the workflow | PR comment, Code Insights, Google Chat, Jira issue, draft PR |

A new config kind, **`Workflow`** (`config/workflows/<id>.yaml`), names the class, the agent
definition, the skills it loads, its principal, its autonomy tier and its delivery channel.
`Trigger` (version-03 P6) binds events to a workflow.

Adding a workflow is a config file, an agent definition and skills. Platform code changes only for
a new event adapter, a new connector or a new delivery channel. That is how the platform extends to
future workflows and actions.

## 2. Principles

These carry over from the POC unchanged, and apply to every workflow class.

1. **Authorization lives in the MCP server.** Agents, enrichment and delivery make no access
   decisions. Configuration declares access. Deny by default, and fail closed.
2. **Calls are made as someone.** A user-led workflow uses the user's token. An event workflow uses
   its own app-only Entra token. A user token never reaches an event workflow, and a service token
   is never used for a user's call.
3. **Event payloads and provider content are untrusted data.** They are handed to agents as data
   and never used verbatim as tool arguments.
4. **Artifacts form a chain, and humans approve at gates** (Playbook): intent → spec → plan → diff
   and tests → PR with review findings → incident record. Each stage commits its artifact, and an
   approved artifact can start the next stage.
5. **Draft with full context, review with none** (EGM): drafting agents load history, architecture
   and knowledge; reviewers run isolated from the drafting context.
6. **Autonomy is tiered.** An event workflow is declared at one tier: `log`, `diagnose`
   (read-only), `propose` (a PR, ticket or runbook for a human to approve) or `act`. `act` is
   reserved and not enabled by this design. Production actions always need a named human approval.
7. **An agent never approves its own output.** Branch protection and code-owner approval apply to
   every PR an agent opens.

## 3. Identity and access

- **Identity provider:** Microsoft Entra ID only. Users sign in with Entra. Workflows authenticate
  with app-only tokens of their own Entra app registration, using federated credentials on GCP
  (version-03 P2).
- **Membership:** Entra security groups and Entra app roles, combined as a union (FR-IDN-002).
- **Platform roles**, bound globally:
  - `viewer`: the common knowledge sources, skills and tools that every engineer shares.
  - `admin`: every platform capability, unconstrained, with the restricted ceiling.
  - Every signed-in user also has `signed-in`, which is only enough to see who they are.
- **Team roles**, bound per team and **effective only within that team**:
  - `member`: every member of the team. The team's skills, tools and knowledge sources, within the
    team's argument limits.
  - `approver` (optional): `member`, plus the team's approval and elevated-access skills and tools,
    and the team's higher-classification sources. For example, only an approver can start the
    implementation workflow.

  Today's ids are `developer` and `lead`. CH-0009 renames them.
- **Team scoping.** A team role grants access only to that team's resources. Being `approver` in
  team A gives nothing extra in team B, and A's classification ceiling doesn't apply to B's
  sources.

  Today's resolver merges every team's roles into one set, so a role leaks across teams: for skills
  gated by role, for sources gated by role, and for the classification ceiling. CH-0009 fixes this.

  Access to dependent systems (GitHub, Bitbucket, Jira, Confluence) is already user-scoped. Connected
  tools use the user's own credentials, so the provider's own permissions apply on top.
- **Workflow principals:** each autonomous workflow has its own role (for example `ci-workflow`,
  `ops-workflow` or `impl-workflow`). The role names the tools, sources and team it may act for, and
  is bound to an Entra app role (version-03 P6 A1).
- **Data access** comes only from each source's access rule, capped by the role's classification
  ceiling and enforced by row-level security (FR-AUTHZ-005, NFR-SEC-005).

**Agent Gateway** is optional and still to be evaluated, for networking and policy enforcement
between the agents in a workflow (for example runtime → MCP server, and agent → agent). If adopted,
it may only **narrow** what the MCP server allows. It never grants access, and the MCP server stays
the authority (NFR-SEC-001). **Agent Registry**
(optional) lists the agents users may reach from Gemini Enterprise. It is a directory, not an
access control.

## 4. Surfaces

| Surface | Protocol | Who | Status |
|---|---|---|---|
| Custom chat UI (`/chat/`, CopilotKit) | AG-UI | Users | Live |
| Gemini Enterprise, Microsoft Copilot and any third-party agent platform | A2A 0.3 (`/a2a`) with the user's Entra token | Users | Gemini Enterprise live; others on the same path |
| Coding harnesses (Antigravity, IDEs, CLI agents) | MCP streamable HTTP, direct to the MCP server, OAuth sign-in | Users | Developer token only today (version-03 P9) |
| Event intake | HTTPS webhooks and push → event gateway | CI tools and ops platforms | Designed (version-03 P6) |

Gemini Enterprise and every third-party agent reach the user-interactive services only through
the A2A endpoint, with the **user's own Entra token**, obtained through Entra OAuth for that user.
There is no platform-level or service token, so every call is authorized as that user.

**Catalogs for coding harnesses.** The MCP server exposes three catalogs, each filtered by the
caller's policy:

- **Tools:** `tools/list`.
- **Skills:** `list_skills` / `load_skill`, and the same skills as MCP prompts or resources, so a
  harness can load them natively.
- **Knowledge:** a new `list_sources` tool lists the sources the caller may read, with their
  classification, type and last ingest time. `search_knowledge` and `graph_query` query them.

A harness sees exactly what the same user sees in the chat.

## 5. Event-driven workflows

```
 CI tools (GitHub Actions, Bitbucket Pipelines, PR webhooks)      Ops (GCP Monitoring, on-prem K8s, Splunk)
                 │                                                            │
                 └────────────────────►  event gateway  ◄─────────────────────┘
                                 verify caller · match Trigger · normalise (CloudEvents)
                                 size-cap · rate-limit · publish · audit
                                                 │
                                     Pub/Sub  sdlc-events-<env>
                                                 │
                                         enrichment service
                     resolve Workflow + team · fetch real-time context (diff, pipeline log,
                     alert, log lines) and agent context (instructions, skills, knowledge refs)
                     through the MCP server, as the workflow principal · publish enriched event
                                                 │
                                     Pub/Sub  (enriched, routed by workflow)
                         ┌───────────────────────┼───────────────────────┐
                   build & test runtime    deploy & maintain runtime   implementation runtime
                   (agent, MCP as          (agent, MCP as              (launches a sandboxed
                    ci-workflow)            ops-workflow)               coding job)
                         └───────────────────────┼───────────────────────┘
                                       structured outcome (Pub/Sub)
                                                 │
                                         delivery service
                         validates the outcome against the Workflow's channel, then posts it:
                         PR comment / check / Code Insights · chat channel · Jira · draft PR
```

The services are split **along credential boundaries**, so each one holds only what its job
needs:

| Service | Holds | Never holds |
|---|---|---|
| Event gateway (public) | Adapter verification secrets, `pubsub.publisher` | MCP access, model access, write tokens |
| Enrichment | Its app-only token, used to call the MCP server | Model access, write tokens |
| Workflow runtimes | Their app-only token and model access | Write tokens, DB credentials, user tokens |
| Delivery | Reporting-only write credentials per channel | Model access |

The agent reads untrusted content, so it is the part most exposed to prompt injection. For that
reason it never holds a credential that can write to an external system. It emits a structured
outcome (typed fields, size-capped), and delivery posts only what the channel's schema allows.

Real-time context, such as the PR diff, pipeline logs, alert details, Kubernetes events and Splunk
searches, is reached through MCP connector tools granted to the workflow's role. These tools keep
authorization, audit and the egress allowlist in one place.

On-premise Kubernetes and Splunk send events to the gateway's push endpoint, with alert webhooks
and the caller verified per adapter. Pulling from them (polling, or queries over a private
connection) is deferred.

Every stage has the reliability rules decided in version-03 P6:
- CloudEvents envelope, with an ordering key per PR or incident.
- A dedupe key per delivery, and `claim_event` through the MCP server.
- Retries with backoff, and a dead-letter topic.
- Run bounds: a timeout, a tool-call cap and a token budget.
- Hop limits on agent-to-agent events.
- One audit record per intake, run and delivery, all linked by a run id.

### Build and test workflows (class 2)

- **Pull request analysis:** summary, risk, the affected components (from the code graph) and
  missing tests.
- **Code quality:** conventions and maintainability, using team skills.
- **Security audit:** secrets, risky dependencies, injection patterns and access changes.
- **Change management:** checks that the change has its approved spec or change record, and that
  the trace and the release notes are complete.

Reviews run as parallel isolated passes (EGM Goldfish), each with its own lens skill. Findings are
graded Blocker, Major or Nit, and are delivered as a PR comment or check. Tier: `diagnose` or
`propose`.

### Deploy and maintain workflows (class 3)

A deterministic alert or log rule starts the workflow. The workflow diagnoses read-only: it
correlates logs, recent deploys and changes, and the runbooks in the knowledge graph.

The finding is delivered in one of two ways, chosen per Workflow:
- **A Jira ticket** in the team's project, with the analysis, the evidence links and a suggested
  action.
- **An alert to the platform admins**, who log the change ticket themselves from the analysis.

The finding is an `intent` that can start class 1. At tier `propose` it also attaches a proposed
runbook step or fix PR, which a human approves.

### Implementation workflow (class 4)

1. **Trigger:** a design or spec artifact is approved. This means an approved or merged spec PR, or
   a Jira transition such as "Approved for build". The person approving must hold `approver` on the
   team.
2. **Plan:** the runtime loads the spec and its change record, then drafts `plan.md` against the
   repository.
3. **Implement in a sandbox:** a Cloud Run Job per run, ephemeral, with:
   - egress only to the repository host and the model endpoint;
   - a short-lived repository token that can push only to a new branch;
   - no production credentials, no DB credentials and no user tokens;
   - a run budget.

   The coding agent is built on **Google ADK** and runs on Google Cloud. It uses the repository's
   own guardrails (agent instructions, skills and tests) and sandbox-local tools: file read and
   write, a shell for builds and tests, and git.
4. **Deliver:** a draft PR that links the spec, the plan and the test results. Architects and
   developers review, modify and approve it under branch protection. The agent can't approve it.
5. **Drift:** after merge, a drift check compares the code with the spec (EGM drift report) and
   files any gaps.

## 6. Knowledge graph

Today: hybrid retrieval over Cloud SQL Postgres. Vector search (pgvector), full-text search
(`tsvector`) and a per-source entity and relation graph, fused at query time. Access is segregated
by source access rules and classification under row-level security, for users and workflow
principals alike.

Extensions:

| Capability | Design |
|---|---|
| **Source code graph** | Parse repositories (tree-sitter) into a symbol graph: files, modules, classes, functions, imports and calls, and owners from CODEOWNERS. Stored per source like the existing graph, joined at query time and under the same RLS. It powers PR impact analysis and implementation planning. |
| **Images and diagrams** | Images and diagrams in documents and repositories (architecture diagrams, screenshots) are described and read with a multimodal model. Opt-in per source and cached like PDF OCR, with the image location cited. |
| **Diverse data** | More loaders: Office documents and SharePoint (version-03 P8), API specifications (OpenAPI), and tables and structured data with schema-aware chunking. |
| **Retrieval accuracy** | Query entity extraction, a re-ranker and per-content-type ranking (version-03 P9). Each change is kept only if the retrieval eval improves or holds, and the eval covers every content type. |

## 7. Conversations and memory

- **Sessions:** in use today. Agent Engine Sessions on GCP (Gemini Enterprise agent platform),
  and SQLite locally, with bounded retention (NFR-PRIV-004).
- **Memory:** optional and deferred (FR-CONV-002 is `parked`). If adopted, it is kept per user, is
  readable only in that user's sessions, and follows the conversation retention rules.

## 8. Technology

| Need | GCP | Local |
|---|---|---|
| Persistent services: app, MCP server, event gateway, enrichment, runtimes, delivery | Cloud Run services | Docker Compose |
| Batch and sandboxed work: ingest, DB setup, reconcile, implementation runs | Cloud Run Jobs | Docker Compose one-off containers |
| Database, vectors, graph | Cloud SQL for PostgreSQL + pgvector | Postgres + pgvector |
| Files: artifacts, config bundles, sources | Cloud Storage | Local volumes |
| Secrets | Secret Manager | `.env` (git-ignored), local secret files |
| Event bus | Pub/Sub (version-03 P6 R3) | Pub/Sub emulator |
| Sessions | Agent Engine Sessions (Gemini Enterprise) | SQLite |
| Memory (optional, deferred) | Agent Engine Memory (Gemini Enterprise) | — |
| Agent directory (optional) | Agent Registry | — |
| Agent networking and policy (optional, to be evaluated) | Agent Gateway | — |
| Implementation coding agent | Google ADK agent on Cloud Run Jobs | Docker one-off container |
| Model | Gemini on Vertex AI | Gemini API or Vertex AI |
| Identity | Microsoft Entra ID | Microsoft Entra ID (dev tenant) |

## 9. Requirements

Added, modified or retired by [CH-0008](../../knowledge/changes/CH-0008.md):

| Topic | Requirements |
|---|---|
| Workflow model | FR-WFL-001 workflows declared and classified |
| Event intake and enrichment | FR-WFL-002 event intake, FR-WFL-003 enrichment, NFR-REL-005 durable event processing |
| Workflow classes | FR-WFL-004 build and test, FR-WFL-005 deploy and maintain, FR-WFL-006 implementation |
| Identity and access | FR-IDN-005 workflow identity; FR-AUTHZ-003 platform and team roles (modified); FR-AUTHZ-006 team roles scoped to their team; NFR-SEC-001 agent gateway may only narrow (modified) |
| Surfaces | FR-SURF-002 third-party platforms use the user's Entra token (modified) |
| Sandbox and delivery | NFR-SEC-012 sandboxed code execution, NFR-SEC-013 agents hold no write credentials |
| Surfaces | FR-SURF-004 catalogs for coding harnesses |
| Knowledge | FR-KNOW-008 source code graph, FR-KNOW-009 images and diagrams, FR-KNOW-010 diverse formats; NFR-QUAL-001 eval covers every content type (modified) |
| Memory | FR-CONV-002 per-user memory (`parked`) |
| Retired | FR-AUTO-001, replaced by FR-WFL-002 to FR-WFL-005 and FR-IDN-005 |

## 10. Decisions

Answered by the user on 2026-11-11:

| # | Question | Decision |
|---|---|---|
| D1 | Ops delivery channel | A Jira ticket, or an alert to the admins, who log the change ticket from the agent's analysis. Chosen per Workflow (FR-WFL-005). |
| D2 | Coding agent for the implementation sandbox | An agent built on Google ADK, running on Google Cloud (FR-WFL-006). |
| D3 | On-premise Kubernetes and Splunk | Push to the gateway's endpoint. Pull is considered later (FR-WFL-002). |
| D4 | Team role names | Rename `developer` to `member` and `lead` to `approver`; `approver` is optional per team. Team roles are effective only within their team (FR-AUTHZ-003, FR-AUTHZ-006, CH-0009). |
| D5 | Third-party agent platforms | Gemini Enterprise and all third-party agents reach the user-interactive services through `/a2a` with the user's Entra token (FR-SURF-002). |
| D6 | Agent Gateway | Optional, to be evaluated for networking and policy enforcement between agents in workflows (NFR-SEC-001). |
| D7 | Memory | Optional and deferred; only sessions are used now (FR-CONV-002 `parked`). |

Still open:

| # | Question | Needed for |
|---|---|---|
| D8 | Which Jira project and issue type each team's ops findings go to, and which channel alerts the admins (Google Chat, email)? | FR-WFL-005 |
| D9 | During the role rename, should both the old and new Entra app-role values be accepted for a transition period? | CH-0009 |

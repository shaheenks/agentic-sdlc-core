# Agentic SDLC — Implementation Plan version-04 (draft)

**Status: draft, proposed 2026-11-11.** This plan builds the
[workflow platform target design](../designs/workflow-platform.md). Version-03 stays the current
plan until the user closes it. This plan then becomes current, and CLAUDE.md is updated to point to
it.

Requirements: change record [CH-0008](../../knowledge/changes/CH-0008.md) and the requirements it
adds. Pending records CH-0001 to CH-0007 and CH-0009 come first (W0). As-built view:
[ARCHITECTURE.md](../ARCHITECTURE.md), [FEATURE_INVENTORY.md](../FEATURE_INVENTORY.md). Earlier
design carried in: [pending-task.md](pending-task.md) task 1 (agent runtimes), and version-03 §P6
(event intake).

## Goals

1. **Workflows as a platform concept.** Workflows are declared in config by class, trigger,
   identity, access and delivery. Each one runs under its own Entra identity, through the same MCP
   policy as users.
2. **Autonomous build and test, and deploy and maintain.** CI and operational events are received,
   enriched, processed by an agent, and delivered as PR findings, Jira tickets or admin alerts. Each
   event produces exactly one outcome.
3. **A gated implementation workflow.** An approver's approval starts a sandboxed Google ADK coding
   agent that delivers a draft PR. Humans review, change and merge it.
4. **Wider reach.** Coding harnesses get the catalogs. Knowledge gains a code graph, images and
   more formats, measured by the retrieval eval.

## How every milestone is done

- **One change record per milestone.** The record names the requirement IDs it builds, and code
  starts only once the user has approved it (`status: stable`, `verified` by `human:`).
- **Tests first** where behaviour is pinned:
  - persona-matrix rows for every new tool and workflow role;
  - `data_rows` for every new source;
  - CODEOWNERS rules for every new config kind.

  CI stays secret-free: fakes, the Pub/Sub emulator, and fake Entra tokens.
- **Finished means:**
  - `uv run sdlc-config validate --env local` passes, with the diff reviewed;
  - `uv run ruff check . && uv run ruff format .` and `uv run pytest` pass;
  - `okf_bundle.py build` and `lint` pass;
  - the requirement and component concepts are updated (`implementation`, `satisfies`,
    `verified_by`);
  - a new workspace member has its component concept;
  - `log.md`, `FEATURE_INVENTORY.md` and this plan are updated as built.
- **The user's actions:**
  - until W0.8 lands, every Terraform step and deploy run. After it, CI deploys every merge to GCP
    dev; the user keeps the first-time steps, the CI/CD bootstrap and approvals of destructive
    plans;
  - every Entra change, confirmed per action with `az account show` first;
  - every external setup: Bitbucket and GitHub test repositories, Jira projects, Splunk or
    Kubernetes test senders, and service tokens.

  This plan lists these steps; the user runs them.
- **Localhost and the tunnel.** Every milestone works on both, and hostnames stay config.

## Phases at a glance

```
W0 Foundation (pending records) ──► W1 Workflow model, identity, service connections
                                        │
                                        ▼
                                    W2 Event pipeline (gateway → enrichment → runtime → delivery)
                                        │
                     ┌──────────────────┼───────────────────┐
                     ▼                  ▼                   ▼
             W3 Build & test     W4 Deploy & maintain   W7 Implementation workflow
                     │                  │                   ▲ (needs W8 first)
                     └────────┬─────────┘                   │
                              ▼                             │
                      W5 GCP rollout of W1–W4        W8 Dedicated MCP backend

 In parallel, any time after W0:  W6 Harness catalogs   ·   W9 Knowledge extensions
```

| Phase | Builds | Waits for |
|---|---|---|
| W0 | CH-0001 to CH-0004, CH-0006, CH-0007, CH-0009 to CH-0011 | User approval of each record |
| W1 | FR-WFL-001, FR-IDN-005, FR-CONN-004 | W0 (CH-0003, CH-0009), CH-0008 approved |
| W2 | FR-WFL-002, FR-WFL-003, NFR-REL-005, NFR-SEC-013 | W1 |
| W3 | FR-WFL-004 | W2, a Bitbucket Cloud test repository |
| W4 | FR-WFL-005 | W2, a Jira project, test alert senders |
| W5 | W1 to W4 on GCP dev | W3, W4 locally; version-03 P2 E4 un-parked |
| W6 | FR-SURF-004, FR-SURF-002 check | W0 |
| W7 | FR-WFL-006, NFR-SEC-012 | W2, W8 |
| W8 | NFR-SEC-014 | W1 |
| W9 | FR-KNOW-008 to FR-KNOW-010, NFR-QUAL-001 | W0 (CH-0001) |

## W0 — Foundation: the pending change records

These clear known defects and debt before new surface is added. Order: specification first, then
tests, then the changes that move config.

| # | Record | Why now | Exit gate | Status |
|---|---|---|---|---|
| W0.1 | CH-0001 built vs live split; CH-0002 one owner per criterion | Spec only; makes the trace honest before it grows | Lint passes; the matrix shows FR-KNOW-006, FR-KNOW-007, FR-CONN-003 as `built` | ✅ done 2026-11-11 (`99972d8`, `d4a0772`); the 9 modified requirements re-approved (`87d8e7a`) |
| W0.2 | CH-0006 tests for unverified components | Pins compose, workspace, user_agent and Terraform claims before W1 to W5 change them | `pytest tests/infra tests/agent/test_user_agent.py` passes with no `.env` and no skips | ✅ done 2026-11-11 |
| W0.3 | CH-0003 retire the SDLC action stubs | Removes fake tools before the real build and test workflows replace them | `sdlc-config diff` shows only the three tools removed | ✅ done 2026-11-11; deployed to GCP dev 2026-11-12 |
| W0.4 | CH-0009 role rename and team scoping | Closes the cross-team role leak; W1's workflow roles build on scoped roles | The cross-team persona loses the leaked access; single-team personas unchanged; Entra app roles switched (user) | ✅ done 2026-11-11; Entra app-role switch and GCP dev deploy done 2026-11-12 (user) |
| W0.5 | CH-0007 specification tooling checks | Needs W0.2 and W0.3 first (its new rules fail on today's bundle) | `pytest tests/knowledge` passes; a workflow file in `verified_by` fails the lint | ✅ done 2026-11-12 |
| W0.6 | CH-0011 membership from app roles only (supersedes CH-0005, which becomes `dropped`) | Removes groups, the group map and the overage path before W1 extends identity with app-only tokens. Switches in the same Entra window as CH-0009 | Every former group persona's access is reproduced by app roles; no `group:` or `groups.yaml` remains; groups claim off (user) | ✅ done 2026-11-11; groups removed from Entra, GCP dev deployed, infra/gcp group + Graph secrets removed (CH-0012) 2026-11-12 (user) |
| W0.8 | CH-0010 continuous deployment to GCP dev | Every later milestone ships through it. First comes a shared deploy manifest, read by `gcp_deploy.ps1` (Windows) and a new `gcp_deploy.sh` (GitHub Actions, Linux), plus a parity test | A config-only merge runs only `config` and the smoke checks; a code merge runs images, plan, apply and smoke; a destructive plan waits for approval | proposed |
| W0.7 | CH-0004 artifact limit counts documents | Independent; can run any time in W0 | New `tests/db/test_artifacts.py` cases pass | proposed |

## W1 — Workflow model, identity and service connections

| # | Scope | Requirements | Exit gate | Size | Status |
|---|---|---|---|---|---|
| W1.1 | Config kinds `Workflow` (`config/workflows/`) and `Trigger` (`config/triggers/`): JSON Schema, `_KINDS`, validation against roles, skills, tools and channels, the `act` tier rejected, CODEOWNERS rules. The user-led flow declared as the first `plan-design` Workflow (descriptive only) | FR-WFL-001 | `sdlc-config validate` accepts the examples and rejects unknown references and `act`; `explain` works for a workflow principal | M | proposed |
| W1.2 | Workflow identity (pending-task §4, version-03 P6 A1): `Principal.kind` (`user` or `workflow`), the MCP verifier accepts app-only tokens only with an app role bound to a workflow role, `service_header_provider` in `sdlc_auth`, block list for workflow principals, and audit `principal_kind` and `workflow_id`. Workflow roles `ci-workflow`, `ops-workflow` and `impl-workflow` in `roles.yaml`, scoped to teams as in CH-0009. Validation: a tool with `credentials.user` is never granted to a workflow role | FR-IDN-005 | A fake app-only token with `SDLC.Workflow.CI` gets exactly the `ci-workflow` tools and sources; an app token without an allowed role gets 401; persona-matrix rows pass | M | proposed |
| W1.3 | Entra (user): one app registration per workflow, and app roles `SDLC.Workflow.CI`, `.Ops` and `.Impl` on `sdlc-mcp`. Local: a dev-only client secret in `.env` | FR-IDN-005 | `whoami` called with a real app-only token returns the workflow principal | S | proposed |
| W1.4 | Service connections: a `service` connection kind in `connections.yaml` (provider, allowed workflows, secret reference); a service-credential path in `sdlc_connectors` for Jira, Confluence and Bitbucket Cloud and Data Center; resolution through `sdlc_secrets` with rotation picked up without a deploy; one set per workflow; audit credential kind `service`; argument limits applied whatever the token allows | FR-CONN-004 | Unit tests: a workflow uses only its own connection; a user call never resolves a service connection; rotation takes effect on the next call; a revoked token answers "not connected" | M | proposed |

## W2 — Event pipeline

This phase follows version-03 §P6 (decisions R1 to R5) and the design's section 5.

| # | Scope | Requirements | Exit gate | Size | Status |
|---|---|---|---|---|---|
| W2.1 | `libs/sdlc_events`: the CloudEvents model, adapter verifiers (GitHub webhook HMAC and Actions OIDC, Bitbucket Cloud and Data Center HMAC, Bitbucket Pipelines OIDC), normalisers, size caps, and a publisher with emulator and Pub/Sub backends | FR-WFL-002 | Unit tests: valid and forged signatures per adapter, wrong repository rejected, payload capped | M | proposed |
| W2.2 | `event_gateway` component (`POST /events/<adapter>`): verify, match a Trigger, rate-limit, publish, `202` + event id, audit `event_intake`. Compose profile `autonomous` with the Pub/Sub emulator; tunnel hostname for webhooks (user: Cloudflare dashboard) | FR-WFL-002 | A real Bitbucket Cloud webhook through the tunnel lands on the emulator as one CloudEvent; a forged one gets 401 and is audited; a disabled Trigger publishes nothing | M | proposed |
| W2.3 | Enrichment service: resolves the Workflow and team from the Trigger, fetches agent context and real-time context (PR diff, pipeline log) through MCP tools as the workflow principal, marks content untrusted, and publishes the enriched event. New read-only MCP connector tools for diffs and pipeline logs, granted to `ci-workflow` | FR-WFL-003 | An enriched event carries the context and the untrusted markers; enrichment holds no model access and no service token (its environment is checked in a test) | M | proposed |
| W2.4 | `libs/sdlc_runner`: push verification, run bounds (timeout, tool-call cap, token budget), dead-letter handling, hop count. MCP tool `claim_event` and migration `agent_runs` (RLS, `tests/db`) | NFR-REL-005 | A redelivered event produces no second run; a run over budget stops and is recorded; dead-lettering works on the emulator | M | proposed |
| W2.5 | Delivery service: typed outcome schemas per channel, posted with the workflow's service connections. Channels: Bitbucket PR comment and Code Insights, GitHub PR comment and check, Jira issue, email. Audit `delivery` | NFR-SEC-013 | A field outside the channel schema is dropped; a runtime has no service token (test); one outcome yields one post | M | proposed |

**Email needs a sender.** The platform has none today. The user picks a mail relay (for example a
Google Workspace SMTP relay, or a mail API), and its credential goes into Secret Manager. Until
then, admin alerts use the admins' Jira queue.

## W3 — Build and test workflows

| # | Scope | Requirements | Exit gate | Size | Status |
|---|---|---|---|---|---|
| W3.1 | `agents/autonomous/ci_agent` with PR analysis (summary, risk, affected components, missing tests). Lens skills run as isolated passes, findings graded Blocker, Major or Nit. Move `agents/user_agent` to `agents/interactive/user_agent` (pending-task §3) | FR-WFL-004 | A PR on the Bitbucket Cloud test repository gets one report, locally through the tunnel; audit shows intake → enrichment → run → delivery with one run id | L | proposed |
| W3.2 | Code quality and security audit Workflows (new lens skills; team-enabled by config) | FR-WFL-004 | Each Workflow can be switched on per team; a seeded secret and a seeded injection pattern are reported | M | proposed |
| W3.3 | Change management Workflow: checks the PR names an approved change record or spec, the trace is complete and the release notes exist | FR-WFL-004 | A PR without a record gets a Major finding; a PR with an approved record passes | S | proposed |
| W3.4 | Injection evals: malicious PR titles, descriptions and diffs | FR-WFL-004 | The eval passes: tool use is unchanged by injected text | S | proposed |
| W3.5 | GitHub adapter and channels (Actions OIDC, PR webhooks, PR comment and check) | FR-WFL-002, FR-WFL-004 | The W3.1 gate on a GitHub test repository | M | proposed |

## W4 — Deploy and maintain workflows

| # | Scope | Requirements | Exit gate | Size | Status |
|---|---|---|---|---|---|
| W4.1 | Push adapters: `gcp-monitoring` (notification channel → `alerts-raw` → gateway with Google-signed OIDC), Kubernetes (Alertmanager webhook, HMAC) and Splunk (alert action webhook, HMAC) | FR-WFL-002 | A test alert from each sender lands as one CloudEvent; open and close are distinct; duplicates are dropped | M | proposed |
| W4.2 | `agents/autonomous/ops_agent`: read-only diagnosis (logs, recent deploys and changes, runbooks from knowledge). New read-only log and deploy-history tools for `ops-workflow` | FR-WFL-005 | A test alert produces a finding with evidence links and no system change | L | proposed |
| W4.3 | Delivery of findings: a Jira ticket in the team's project and issue type (new team-config keys), or an admin alert to the admins' Jira queue or email (platform config) | FR-WFL-005 | Each team's test alert opens a ticket in its own project; an admin alert reaches the configured queue or address | S | proposed |
| W4.4 | Tier `propose`: attach a runbook step or fix PR for approval | FR-WFL-005 | A proposal needs a named approval; nothing is changed without one | M | proposed |

## W5 — GCP rollout of W1 to W4

| # | Scope | Exit gate | Status |
|---|---|---|---|
| W5.1 | Un-park version-03 P2 E4: federated credentials, so each workflow's Cloud Run service account is trusted by its Entra app (FR-IDN-005: no client secrets on GCP). Entra changes by the user | A workflow on GCP gets an app-only token without a client secret | proposed |
| W5.2 | Terraform (applied by the CI deploy from W0.8, merged as code; a destructive plan waits for the user's approval): topics and subscriptions (filters, ordering, dead letter); services for the gateway, enrichment, runtimes and delivery, with one service account each; the notification channel; Secret Manager entries for service connections; Cloud Run egress settings | `plan` shows only the new resources; `apply` passes | proposed |
| W5.3 | Rollout through the CI deploy: images, plan and apply, `db` (`agent_runs`) and `config` (new kinds, roles, connections) run automatically on merge | The W3.1 and W4.3 gates pass on GCP dev | proposed |

## W6 — Catalogs for coding harnesses

| # | Scope | Requirements | Exit gate | Size | Status |
|---|---|---|---|---|---|
| W6.1 | `list_sources` tool (readable sources with type, classification and last ingest time); skills also exposed as MCP prompts or resources | FR-SURF-004 | Persona tests: each persona sees exactly its sources and skills; hidden ones are not disclosed | S | proposed |
| W6.2 | OAuth sign-in from harnesses (version-03 P9: Antigravity) through Entra | FR-SURF-004 | Antigravity signs in as a user and sees the same catalogs as the chat | M | proposed |
| W6.3 | A2A check for third-party platforms: a test that `/a2a` refuses anything but a valid user token, and onboarding notes for Microsoft Copilot | FR-SURF-002 | The test passes; Copilot reaches `/a2a` as the user when onboarded | S | proposed |

## W7 — Implementation workflow

| # | Scope | Requirements | Exit gate | Size | Status |
|---|---|---|---|---|---|
| W7.1 | Sandbox image and job: a Cloud Run Job (locally, a one-off container) with egress only to the model endpoint and declared registries; a service account with only the Vertex AI role; no external credentials | NFR-SEC-012 | Tests and a live check: no credentials in the environment; calls to other hosts fail; the job is destroyed after the run | M | proposed |
| W7.2 | `agents/autonomous/impl_agent` on Google ADK: plan from the spec and its change record, then implement with sandbox-local tools (file read and write, shell for builds and tests, git), within a run budget, returning a patch, the plan and the test results | FR-WFL-006 | On a sample repository and an approved sample spec, the agent returns a patch whose tests pass | L | proposed |
| W7.3 | Trigger and delivery: an approved or merged spec PR, or a Jira transition, by a team `approver` starts the run. The runtime prepares the checkout, then pushes a new branch and opens a draft PR through the MCP backend (W8) | FR-WFL-006 | An approval by a `member` starts nothing; an approval by an `approver` yields one draft PR linking the spec, the plan and the tests; the agent cannot approve it | M | proposed |
| W7.4 | Drift check after merge (code vs spec), filing gaps | FR-WFL-006 | A seeded divergence is reported | S | proposed |
| W7.5 | GCP rollout (user: Terraform, deploy) | — | The W7.3 gate on GCP dev | S | proposed |

## W8 — Dedicated MCP backend

The implementation workflow is the first to hold a broad write token (Bitbucket). It gets its own
backend, so that token lives in no other process.

| # | Scope | Requirements | Exit gate | Size | Status |
|---|---|---|---|---|---|
| W8.1 | `core_mcp` serves only the tools of its `tools.yaml` server, and refuses others as unknown; per-backend token audience in config | NFR-SEC-014 | A tool assigned to another server is unknown on `core-mcp`; every existing test still passes | S | proposed |
| W8.2 | `mcp_servers/impl_mcp`: a sibling component on the shared libraries, serving the implementation workflow's repository tools with its own service connections and, optionally, its own Entra app | NFR-SEC-014 | `impl-workflow` reaches only `impl_mcp`; `core-mcp` holds no Bitbucket write token; one policy and one audit format | M | proposed |

## W9 — Knowledge extensions

| # | Scope | Requirements | Exit gate | Size | Status |
|---|---|---|---|---|---|
| W9.1 | Eval coverage first: questions per content type in `tests/evals` | NFR-QUAL-001 | The eval reports a score per content type | S | proposed |
| W9.2 | Source code graph: tree-sitter parsing (Python and TypeScript first) into symbols, imports, calls and CODEOWNERS owners, per source under RLS; a code query in `graph_query` | FR-KNOW-008 | "Which symbols does this change affect?" is answered with file and line citations; the eval holds or improves | L | proposed |
| W9.3 | Images and diagrams: multimodal description, opt-in per source, cached by hash | FR-KNOW-009 | Image chunks cite their location; non-opted-in sources skip images and count them | M | proposed |
| W9.4 | Office and SharePoint, OpenAPI and tabular loaders (with version-03 P8) | FR-KNOW-010 | Each format chunks by its structure; the eval holds or improves | M | proposed |
| W9.5 | Live checks from CH-0001 (Atlassian sources and connections, OCR), with version-03 P8 | FR-KNOW-006, FR-KNOW-007, FR-CONN-003 | Each set to `live` after a recorded run | S | proposed |

## Not in this plan

- **Agent Gateway** (design D6): evaluated after W5, when there is traffic between agents to put
  policy on.
- **Memory** (FR-CONV-002, `parked`): sessions only.
- **Pulling from Kubernetes and Splunk**: push only for now.
- **OAuth or system principals for providers**: they replace the broad service tokens later,
  without changing FR-CONN-004.
- **Autonomy tier `act`**: rejected by validation.
- **User-confirmed write tools** (FR-WRITE-001, version-03 P7), **production operations**
  (NFR-OPS-001, version-03 P3) and **scale-out stores** (NFR-REL-003): these stay in version-03 or
  its successor. NFR-REL-003 becomes urgent once W5 runs more than one instance of a service.

## Prerequisites from the user

| # | Needed | For |
|---|---|---|
| U1 | Approval of CH-0008, then of each W0 record | W0, W1 |
| U2 | A Bitbucket Cloud test repository and workspace, and a service token for the CI workflow | W2.2, W3 |
| U3 | A Jira site and project per team, an admin queue, and a service token per workflow | W4.3 |
| U4 | Test senders: a GCP alert policy, a Kubernetes Alertmanager and a Splunk alert action reaching the tunnel | W4.1 |
| U5 | A mail relay for the email channel, or Jira-only admin alerts until it exists | W2.5, W4.3 |
| U6 | Entra: workflow app registrations and app roles (W1.3), then federated credentials (W5.1) | W1, W5 |
| U7 | A GitHub test repository, for W3.5 | W3.5 |
| U8 | A sample repository and spec for the implementation workflow | W7.2 |

## Open questions

| # | Question | Needed for |
|---|---|---|
| V1 | Order after W2: W3 and W4 in parallel, or W3 first (CI is easier to test with a webhook than ops is with alerts)? Proposal: W3 first. | W3, W4 |
| V2 | Runtimes: one Cloud Run service per workflow class, or one runtime hosting all autonomous agents (pending-task §11.4)? Proposal: one per class, each with its own identity and limits. | W2.4, W5 |
| V3 | Does this plan become current when W0 starts, or after version-03 is closed? | — |

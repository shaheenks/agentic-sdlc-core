# Agentic SDLC — Implementation Plan version-03 (draft)

**Status: draft (2026-11-05).** Becomes the current plan when version-02's close-out checklist
([version-02.md](version-02.md) §20) is done. Scope and order are a proposal to confirm milestone by milestone;
nothing here is built.

Follows [version-02.md](version-02.md). Architecture: [../ARCHITECTURE.md](../ARCHITECTURE.md); GCP runbook:
[../GCP_DEPLOYMENT.md](../GCP_DEPLOYMENT.md); secrets: [../SECRETS_REVIEW.md](../SECRETS_REVIEW.md); designs carried in:
[pending-task.md](pending-task.md) (tasks 1 and 3).

## Goals

1. **Production-shaped GCP:** a staging environment without dev shortcuts, enterprise identity (app roles,
   federated credentials, Entra apps in Terraform), custom hostnames, CI deploys.
2. **Richer agent output:** A2UI citation cards and an A2A endpoint (the GO from the version-02 N7 spike), and
   stored artifacts users can download.
3. **Autonomous agents:** CI and ops agents with their own workload identity, read + report back.
4. **More sources and connectors,** live-checked: Atlassian Cloud, Data Center editions, private repos.

## Milestones (proposal)

| # | Milestone | From | Waits for |
|---|---|---|---|
| P0 | Carry-in: anything from version-02 §20 that failed and was moved here | version-02 §20 | version-02 close-out |
| P1 | Staging environment | N5, D4 | Q1 (project, region, hostnames); billing go-ahead |
| P2 | Enterprise identity: app roles defined in the tenant (E1), federated credentials instead of client secrets (E4), Entra apps in Terraform (E5), no Azure CLI pre-auth outside dev (E6), per-environment Entra client | N5, version-00 E1/E4–E6, SECRETS_REVIEW §6 | Entra admin, confirmed per change |
| P3 | Operations: custom hostnames + managed certificates (drop the `*.run.app` exception), CI deploy stages (build → plan → apply with approval), Cloud SQL private IP, scale out `sdlc-app`, shared rate-limit store (if `sdlc-mcp` > 1 instance), log-based metrics + alerts on audit events, Secret Manager data-access logs | N5, N4, SECRETS_REVIEW §6 | P1 for staging parts |
| P4 | A2UI citation cards in `/chat/` + A2A endpoint | N7 spike (version-02 §10 "Spike findings") | — |
| P5 | Artifacts: store, list and download agent-generated files under RBAC | pending task 3 | Q4 (use cases, storage) |
| P6 | Agent runtimes: `ci_agent`, `ops_agent` with workload identity, read + report back | pending task 1, D7 | Q5 (trigger sources, report channels) |
| P7 | Write tools on behalf of the user (create issue, comment, PR) with UI confirmation | N6, D5 | P6 decisions (approval gates) |
| P8 | Connectors and sources: Atlassian Cloud live checks (incl. AG-UI gate 5 Jira part), Data Center editions (Bitbucket DC "who am I"), Cloud + DC side by side, URL elicitation, PDF OCR live check (a source with scanned PDFs), source secrets in Secret Manager (first private source), SharePoint / Office documents, GitHub App tokens, `inherit_from_source` | N2, N6 | Q3 (Atlassian site, DC instance, private sources) |
| P9 | Quality and tooling: ADK evals in CI, retrieval ranking (re-ranker, query entities), `explain` by UPN, Antigravity OAuth sign-in + Stage 8 gate, OBO where providers support it, OPA/Cedar if rules outgrow YAML, admin UI over config | N6, version-00 Stage 8/9 | — |
| — | Per-source Entra group `infra-readers` (or a real one) in the tenant | N9 | a source that needs its own group |
| — | Gemini Enterprise registration (A2A agent + OAuth authorization) | version-02 §7 | org admin, workforce pool, licences; P4 |

**Suggested order:** P0 → P4 (no outside dependencies, builds on the spike) → P1 + P2 (staging with enterprise
identity from day one) → P3 → P5 / P6 / P7 as their decisions land; P8 and P9 picked by priority alongside.

## Open questions

| # | Question | Needed for |
|---|---|---|
| Q1 | Staging: GCP project, region, hostnames (`<service>-sdlc-staging.shaheenks.co.in`), who approves applies | P1, P3 |
| Q2 | Order of P1–P9; what "done" means for version-03 | all |
| Q3 | Atlassian Cloud site and a Data Center instance for live checks? Which private repos / sources? | P8 |
| Q4 | Artifacts: first use cases, storage (GCS + Postgres metadata proposed), retention, sharing scope | P5 |
| Q5 | Agent runtimes: trigger sources (GitHub Actions, Bitbucket Pipelines, Cloud Monitoring, webhooks), report channels | P6, P7 |
| Q6 | Write tools: which first, and the approval model (per call, per session, per team policy) | P7 |

## Rules that carry over

All CLAUDE.md rules stay: authorization in the MCP server only, deny by default, config-declared access, the user runs
Terraform and the deploy script, Entra changes need confirmation per action, dev shortcuts never reach staging/prod.
New for version-03: staging and prod use no client secrets in `.env` (P2) and no `*.run.app` URLs (P3).

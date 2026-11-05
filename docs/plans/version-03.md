# Agentic SDLC — Implementation Plan version-03 (draft)

**Status: current (2026-11-05).** Started before version-02's last close-out item (§20 H6, the first scheduled
ingest/reconcile runs) by the user's decision; H6 is checked alongside. First milestone: **P5 artifacts** (§P5).
Other milestones remain a proposal, confirmed one by one.

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

**Order (decided 2026-11-05):** P5 first (Q4 answered). Then proposed: P4 (no outside dependencies) → P1 + P2
(staging with enterprise identity from day one) → P3 → P6 / P7 as their decisions land; P8 and P9 by priority.

## P5 — Artifacts (from pending task 3)

**Decisions (2026-11-05, Q4):**

| # | Decision |
|---|---|
| A1 | First use cases: **design / review documents** and **user stories / reports**, as text files (Markdown first) |
| A2 | Metadata in **Postgres** (`sdlc.artifacts`); `sdlc_app` gets a **narrow write grant on that table only** (SELECT, INSERT, DELETE), row-level security by owner oid. Knowledge tables stay read-only for `sdlc_app` |
| A3 | **Owner only.** Anyone else (admins included) gets "not found". Team sharing + classification inheritance = a later milestone (F3) |
| A4 | Retention **7 days** from creation, as the GCP artifact bucket's lifecycle today (`artifact_retention_days`) |
| A5 | Written and read **through the MCP server** (tools + an HTTP download API), never through ADK's artifact service (stays `memory://`), so there is one audited path |

**Design:**
- **Content store** (`libs/sdlc_artifacts`): put / get / delete by object key `artifacts/<owner oid>/<artifact id>`;
  backends `file://<folder>` (compose volume on `core-mcp`, like the user secret store) and `gs://<bucket>/<prefix>`
  (GCP). Selected by `SDLC_ARTIFACT_STORE`; empty = artifacts off (tools answer "not configured").
- **Metadata** (migration `005_artifacts.sql`): `id` uuid, `owner_oid`, `name`, `media_type`, `size_bytes`, `sha256`,
  `agent_session_id` (correlation only), `created_at`, `expires_at`. RLS ENABLE + FORCE; policy for `sdlc_app`:
  `owner_oid = current_setting('app.user_oid')`, set per transaction by `sdlc_db.owner_scoped(conn, oid)` from the
  verified token. No grant to `sdlc_ingest`. Not knowledge data, so no `source_id` / `classification_rank` yet (F3
  adds classification for sharing).
- **MCP tools** (`tools.yaml`, granted to `viewer` and up, persona-matrix rows): `save_artifact(name, content,
  media_type="text/markdown")` → id, size, expiry, download path; `list_artifacts()`; `read_artifact(id)` (the agent
  revises a document); `delete_artifact(id)`.
- **Limits:** text media types only (`text/markdown`, `text/plain`, `text/csv`, `application/json`), 1 MiB per
  artifact, 50 live artifacts per user, file names `[A-Za-z0-9._ -]`, max 100 characters, with a matching
  extension. Expired rows are not listed and are deleted on the owner's next save/list.
- **Download API** on the MCP server, through oauth2-proxy like `/connections/`: `GET /artifacts/` (list),
  `GET /artifacts/{id}` (download: `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`, never
  rendered as HTML on our origin), `DELETE /artifacts/{id}` (needs `X-SDLC-Request: 1`). Same token checks as MCP
  (block list included); the caller's policy must allow `list_artifacts` / `read_artifact`.
- **Audit:** `artifact_change` (create / delete: oid, artifact id, media type, size, outcome) and `artifact_access`
  (download / read: oid, artifact id, outcome); never the content or the file name. Tool calls are also in `tool_call`.
- **Chat:** the agent links the download path (`/artifacts/<id>`) in its answer; the chat app needs no new data path.

**Milestones:**

| # | Scope | Exit gate | Status |
|---|---|---|---|
| F1 | `libs/sdlc_artifacts` (file + GCS), migration 005 + `owner_scoped`, MCP tools, config + persona rows, compose volume | Tests: a user saves, lists, reads and deletes their own artifact; another user gets "not found"; limits enforced; RLS test in `tests/db`; audit records | ✅ Built 2026-11-05: `tests/db/test_artifacts.py` (RLS + tools end to end), `tests/artifacts/`; migration 005 applied to the local dev DB, core-mcp logs `artifacts on (file store, 7.0 days)`; full suite 779 passed. GCP: needs `-Step db` (migration) with F4 |
| F2 | Download API + oauth2-proxy routes (localhost **and** the tunnel) + agent instruction to link artifacts | A download works on localhost and the tunnel; no access without a session; another user's id answers 404 | 🔨 Built 2026-11-05: `artifacts_api.py` (GET list / GET download / DELETE with `X-SDLC-Request: 1`; 401 without token, 403 without the tool, 404 for others' ids; attachment + `nosniff` + CSP sandbox), proxy upstream (both local proxies answer 302 to sign-in), agent instruction, chat card for `save_artifact` / `list_artifacts` (links built from the UUID only). Tests: `tests/db/test_artifacts.py`, UI `results.test.ts`. Open: your live check in the chat on localhost and the tunnel |
| F3 | Team sharing + classification inheritance | later (A3) | not planned |
| F4 | GCP: MCP service account gets `objectUser` on the artifact bucket (the agent's grant is removed), `SDLC_ARTIFACT_STORE` on `sdlc-mcp`, proxy routes; Terraform run by the user | F1/F2 gates on GCP dev | open |

## Open questions

| # | Question | Needed for |
|---|---|---|
| Q1 | Staging: GCP project, region, hostnames (`<service>-sdlc-staging.shaheenks.co.in`), who approves applies | P1, P3 |
| Q2 | Order of P1–P9; what "done" means for version-03 | all |
| Q3 | Atlassian Cloud site and a Data Center instance for live checks? Which private repos / sources? | P8 |
| Q4 | ~~Artifacts: first use cases, storage, retention, sharing scope~~ answered 2026-11-05 (§P5 A1–A5) | P5 |
| Q5 | Agent runtimes: trigger sources (GitHub Actions, Bitbucket Pipelines, Cloud Monitoring, webhooks), report channels. Option raised 2026-11-05: try `ci_agent` / `ops_agent` first as dev-only folders in the existing ADK web app (they run as the signed-in user, so this tests prompts, skills and report format, not workload identity or triggers) | P6, P7 |
| Q6 | Write tools: which first, and the approval model (per call, per session, per team policy) | P7 |

## Rules that carry over

All CLAUDE.md rules stay: authorization in the MCP server only, deny by default, config-declared access, the user runs
Terraform and the deploy script, Entra changes need confirmation per action, dev shortcuts never reach staging/prod.
New for version-03: staging and prod use no client secrets in `.env` (P2) and no `*.run.app` URLs (P3).

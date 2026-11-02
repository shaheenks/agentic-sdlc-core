# Agentic SDLC — Implementation Plan version-02

Follows [version-01.md](version-01.md) (new sources, AG-UI web app, user connections, GCP dev, M0–M8) and
[version-00.md](version-00.md) (Stages 0–9, local backlog H1–H10). Architecture: [../ARCHITECTURE.md](../ARCHITECTURE.md);
GCP runbook: [../GCP_DEPLOYMENT.md](../GCP_DEPLOYMENT.md).

Version-02 collects everything still open from both earlier plans: what version-01 left pending or deferred
(§10.3, §10.4, §6) and what version-00 left open (Stage 7b operations, Stage 8 surfaces, the Stage 9 backlog, the
enterprise gaps E1–E10). §9 maps every carried-over item to its milestone. Nothing here is built yet; scope and order
are a proposal to confirm milestone by milestone.

## Goals

1. **Real knowledge on GCP dev:** the dev sources ingested on Cloud Run, with credentials in Secret Manager and a schedule.
2. **Connectors proven against live systems:** GitHub, Bitbucket, GCS, Confluence and Jira (Cloud and Data Center), both as
   ingest sources and as user connections; retrieval measured per source type. This closes the version-01 exit gate.
3. **Secrets and revocation reviewed and hardened:** block list on GCP, user-secret lifecycle (reconcile job), secret checks.
4. **Operable GCP:** tracing, scale-out, config bundles with reload, CI deploys, custom hostnames; ready for a staging
   environment.
5. **Product backlog** picked by priority: conversation history in the chat app, Cloud + Data Center side by side, write
   tools (decision), Gemini Enterprise (still deferred until its prerequisites exist).

## Progress

| Milestone | Status | Notes |
|---|---|---|
| N0 — Carry-over checks | ⏳ | version-01 §10.4 checks not yet confirmed on localhost / the tunnel (G1, G2, G5, G7) |
| N1 — Dev sources on GCP + ingest | ⏳ | Needs the list of sources (§1) |
| N2 — Live connector checks + retrieval eval | ⏳ | Needs test instances and tokens (§2, §8) |
| N3 — Block list and secret management review | ⏳ | Review first, then build (§3) |
| N4 — Observability on GCP | ⏳ | Cloud Trace export (§4) |
| N5 — GCP operations (Stage 7b) | ⏳ | Scale-out, bundles + reload, CI deploy, hostnames, staging (§5) |
| N6 — Product backlog | ⏳ | Pick items per priority (§6) |
| N7 — Agent-generated UI (A2UI) + A2A path for Gemini Enterprise | ⏳ | Approved 2026-10-30; spike first, keep CopilotKit (§10) |
| N8 — Chat UX | ✅ Built (2026-10-30); answer rendering confirmed by the user | Answer formatting, `/` opens the chat, navbar user + PAT status (§11). Open: navbar and `/` check in the browser, GCP `images` + `plan` + `apply` |
| N9 — Per-source Entra groups | ✅ Built (2026-11-02) | Sources grant by their own Entra group or `everyone: true`; `graph_query` moved to viewer (§12). Open: real `infra-readers` group in the tenant |
| N10 — Direct members by email (users.yaml) | ✅ Built (2026-11-02) | Users added to teams/roles in git-ignored `users.yaml`, matched by oid; `sdlc-config users sync`; GCP secret mount (§13). Open: GCP `plan` + `apply`, live check |
| Deferred — Gemini Enterprise | ⏸ | Design in version-01 §6; needs an org admin, a workforce pool and licences |

**Next:** N0 (quick, local), then N1 once the dev sources are decided.

## Open decisions

| # | Question | Needed for |
|---|---|---|
| D1 | Which sources does GCP dev get? (keep the sample folders? `sdlc-platform`: https GitHub location or drop it? which GitHub/Bitbucket repos, GCS bucket, Confluence space, Jira project; their secret names) | N1 |
| D2 | Which Atlassian Cloud site replaces the `acme.atlassian.net` placeholder in `config/connections.yaml`? Is a Data Center test instance available? | N2 |
| D3 | Block list and secret management: scope of the review (§3); one user secret per user stays, or move to one per connection / a separate credential service? | N3 |
| D4 | A staging environment in version-02, or dev only? (project, region, hostnames) | N5 |
| D5 | Write tools on behalf of the user (create issue, comment, PR): in version-02 or later? | N6 |
| D6 | Replace CopilotKit with an own chat client (`@ag-ui/client` + `@a2ui/react`)? **Not pursued** (2026-10-30): no Gemini Enterprise benefit (GE has its own UI); it would only remove the Node runtime and its workarounds at the cost of owning a chat UI. Revisit if the CopilotKit runtime becomes a burden | — |

## 1. Dev sources on GCP + ingest (N1)

From version-01 §10.3 and §5.1. Config is baked into the images (`SDLC_CONFIG_WATCH=false`), so every sources change is
`images` + `plan` + `apply` before the `ingest` step. The user runs Terraform and the deploy script.

- Update `config/sources/` for dev (D1). `sdlc-platform` reads this repository's `.git`, which the ingest image does not
  contain: point it at an `https` location with `provider: github` (pinned SHA stays for the eval) or leave it out of dev.
- Remote hosts in `platform.yaml` `knowledge.allowed_hosts` (Confluence attachments also need `api.media.atlassian.com`).
- **Source credentials in Terraform:** one Secret Manager secret per `{secret: name}` reference, with
  `secretAccessor` for the jobs service account only. `{secret: name}` is looked up as the secret id `name` itself
  (no `sdlc-<env>-` prefix): decide whether to keep that or add an env prefix in `sdlc_secrets` (then local `env`
  mapping stays the same). Values are set outside Terraform (no secrets in state), e.g. `gcloud secrets versions add`.
- GCS buckets in `gcs_source_buckets`.
- **Cloud Scheduler** triggering `sdlc-ingest-<env>` per source group (the Source `schedule` field becomes a cron).
- Each new source: persona-matrix `data_rows`, CODEOWNERS rule, `sdlc-config diff` reviewed.
- Gate: ingest succeeds on GCP; per persona, `search_knowledge` / `graph_query` return only readable sources, with
  citations linking to the right file/page/issue.

## 2. Live connector checks + retrieval eval (N2)

Connectors were built and tested against fakes only (version-01 §2, §4.8–4.10). Live checks need the prerequisites in §8.

- **Ingest sources:** one GitHub repo, one Bitbucket repo per edition, one GCS bucket, one Confluence space and one Jira
  project per edition. Check first: Confluence Cloud v1 CQL search (Atlassian is retiring v1 endpoints; fallback = v2
  listing by space + per-page restriction calls), Cloud attachment download redirects, Jira Cloud `search/jql`
  paging, the `security` field with and without issue security, Bitbucket DC links behind a context path.
- **User connections:** Jira and Confluence Cloud (`atlassian` connection, after D2); every Data Center edition (needs
  config entries, version-01 §4.9). Verify the Bitbucket DC "who am I" endpoint (`/plugins/servlet/applinks/whoami`,
  undocumented; fallback = an authenticated REST call that returns the user).
- **PDF OCR (version-00 H10):** built but never checked live; run a source with `spec.ingest.pdf.ocr: gemini`
  (`platform-infra`'s scanned notices) on GCP and check page citations.
- **Retrieval eval:** questions per new source type in `tests/evals/retrieval_questions.yaml` (vector vs hybrid).
- **Remaining AG-UI gate items** (version-01 §7): gate 3 (answers cite Confluence/Jira/GitHub sources by URL; users
  without access never see them); gate 5 Jira part (connect a Jira PAT, a second user whose provider account lacks
  access gets the provider's denial); gate 2 with Antigravity.

## 3. Block list and secret management review (N3)

Review first (D3), then build what the review keeps. Candidates from version-01:

- **Block list on GCP:** today no `blocked.yaml` is mounted on the MCP service. Store it in Secret Manager and mount it
  as a file like `groups.yaml`; decide how it updates without a redeploy (new secret version + reload) and whether the
  agent (`sdlc_web`) should also refuse blocked users before calling the MCP server.
- **Reconcile job** (version-01 §4.7): delete user secrets of blocked users, expired tokens, connections left
  `invalid`, users not seen for 90 days. Note: `max_token_days` (90) already caps every token, so expiry cleanup covers
  most stale connections without tracking "last seen" per call. Cloud Run job with the MCP service account + Cloud
  Scheduler; locally a CLI with `--dry-run`. Audit `connection_change` with actor `reconcile`.
- **`sdlc-config validate --check-secrets`:** every `{secret:}` / `{env:}` reference resolves (exists), values never
  printed; needs cloud access, so not in CI.
- **User secrets:** Secret Manager data-access audit logs on; optional CMEK; re-check the custom role and its name-prefix
  condition; revisit one-secret-per-user vs one-per-connection or a separate credential service (version-01 §9).
- **Global secrets:** rotation procedure (5-minute cache, re-read after 401) written down and tried once.
- **Revocation latency (version-00 E3, still open):** the `oid` block list exists; short token lifetime policy and CAE
  claims challenges do not. Decide whether a token lifetime policy (tenant change, admin-confirmed) is worth it.

## 4. Observability on GCP (N4)

- OTLP export from agent and MCP to **Cloud Trace** (locally Jaeger). Same rules as locally: one agent turn = one trace,
  no prompts, responses, tokens or argument values in spans; audit records keep `trace_id`.
- Log-based views for the audit events (`tool_call`, `auth_failure`, `connection_change`) in Cloud Logging.

## 5. GCP operations, Stage 7b (N5)

From GCP_DEPLOYMENT §10 and version-00 Stage 7:

- **Scale out `sdlc-app`:** conversations are in Agent Engine (version-01 M8); confirm oauth2-proxy cookie sessions are
  enough, then raise `app_max_instances`.
- **Shared rate-limit store** when `sdlc-mcp` runs more than one instance (limits are per instance today).
- **Config bundles on GCS** with a `current` pointer and Pub/Sub reload (compile/activate/rollback exist locally), so
  config changes no longer need new images.
- **CI deploy stages:** build → plan → apply (validate, diff and tests already run on GitHub Actions); the user approves
  applies.
- **Custom hostnames** `<service>-sdlc-<env>.shaheenks.co.in`: CNAME + Google-managed certificate, then drop the
  `*.run.app` exception.
- **Cloud SQL private IP.**
- **Staging** (D4): a second environment with its own tfvars/state/groups, Entra callback, and no dev shortcuts.
- **Enterprise readiness** for staging/prod (version-00 gaps): E4 certificates or federated credentials (Entra trusts
  GCP workload identity) instead of client secrets; E5 Entra apps in Terraform (`azuread`) with a reviewable manifest;
  E6 no Azure CLI pre-authorization outside dev (`entra_setup.ps1 -NoAzCliPreAuth`); a per-environment Entra client
  app; E1 app roles defined in the tenant (code and config support them since Stage 3) before onboarding real users
  with large group claims.
- **Stage 7b gate (version-00):** a config change is promoted by bundle + pointer flip without a redeploy; rollback by
  pointer.

## 6. Product backlog (N6)

- **Chat app:** load conversation history after a reload (`/agents/state`) and a thread list per user (version-01 §3.1
  known limitations).
- **Connections:** several connections per tool so Cloud and Data Center of one product can be offered side by side
  (version-01 §4.9); MCP URL elicitation for "not connected" where the client supports it.
- **Write tools** on behalf of the user (D5): create issue, comment, PR. Each needs policy, UI confirmation (UX, never
  authorization) and its own review; provider content stays untrusted.
- **Surfaces (version-00 Stage 8):** Antigravity OAuth sign-in through the MCP server's protected-resource metadata and
  the pre-registered `sdlc-client` (enterprise path; today it uses an Azure CLI dev token); then the Stage 8 gate (same
  `whoami(explain)` in adk web, the chat app and Antigravity).
- **Sources (version-00 Stage 9):** a `sharepoint` source type; Office documents (docx, xlsx, pptx); chunking by
  definition for more code languages; GitHub App installation tokens (needs a minting step); mirroring native ACLs
  (`access.inherit_from_source: true`) instead of skipping restricted items.
- **Config tooling:** `sdlc-config explain` by UPN (lookup through the Graph fallback; today personas and group aliases).
- **Quality:** ADK evals in CI; retrieval ranking (query-entity extraction, re-ranker) measured on `tests/evals`.
- **Access model:** Entra OBO for downstream calls where a provider supports it; OPA/Cedar if rules outgrow YAML; an
  admin UI over config (still git-backed).

## 7. Deferred: Gemini Enterprise

**Preferred path (2026-10-30, §10):** register the agent as an **A2A agent** (Cloud Run) with an **OAuth authorization
against Entra** (`serverSideOauth2`: `clientId`, `clientSecret`, `authorizationUri`, `tokenUri`; scope
`api://<sdlc-mcp>/access_as_user offline_access` in the authorize URI). GE then sends the user's token in
`Authorization: Bearer`, which `sdlc_web`'s middleware already validates, and renders the agent's A2UI natively. No
token in session state, no configurable state key. Sign-in to GE itself still needs WIF with Entra as OIDC provider.

**Alternative:** the version-01 §6 design (agent on Agent Runtime, token in session state under the authorization id).
Agent Engine sessions (version-01 M8) are the store either way.

Still deferred: needs a GE app and licences, an org admin for the workforce pool, and GE's A2A agent registration is
**Preview** (Pre-GA terms). N7 makes the agent ready in the meantime.

## 8. Prerequisites to arrange

| Needed | For | Who |
|---|---|---|
| The list of dev sources, their URLs and secret names (D1) | N1 | You |
| Read-only tokens: GitHub fine-grained PAT, Bitbucket Cloud repository access token, Bitbucket DC HTTP access token | N1, N2 | Repo owners |
| A GCS bucket with sample documents in `sdlc-demo-env01` (your go-ahead) | N1, N2 | GCP project owner |
| Atlassian Cloud test site (D2) + a Confluence/Jira Data Center instance with PATs enabled | N2 | Atlassian admin |
| Approval for new billable GCP resources (Cloud Scheduler, a staging environment) | N1, N5 | You |
| Entra admin changes (per-environment client, certificates, app roles) | N5 | Entra admin (confirmed per change) |
| GCP organization admin, workforce pool, Gemini Enterprise licences | Deferred | Org admin |
| A GE app + a new Entra client registration with GE's OAuth redirect URI (for the A2A agent authorization) | Deferred (§7) | Entra admin (confirmed per change) |

## 9. Carried over

| From | Item | Milestone |
|---|---|---|
| version-01 §10.4 | Exit-gate checks G1, G2, G5, G7 on localhost / the tunnel | N0 |
| version-01 §10.3 | Dev sources + ingest on GCP, source secrets in Terraform, GCS buckets, Cloud Scheduler | N1 |
| version-01 §7, §8, §9 | Live checks of every connector (ingest + user connections, Cloud and DC), retrieval eval per source type, AG-UI gate items 2 (Antigravity), 3 and 5 (Jira) | N2 |
| version-01 §4.9 | Bitbucket DC "who am I" endpoint unverified; DC connections not configured | N2 |
| version-01 §10.3, §4.7 | Block list on GCP, reconcile job, `--check-secrets`, user-secret review | N3 |
| version-01 §10.3 | Cloud Trace export | N4 |
| version-01 §3.1, §4.9, §4.5 | Chat history reload + thread list; Cloud + DC per tool; URL elicitation; write tools | N6 |
| version-01 §6 | Gemini Enterprise (WIF, Agent Runtime, OAuth authorization) | Deferred |
| version-00 H10 | PDF OCR live check | N2 |
| version-00 E3 | Short token lifetimes, CAE claims challenges | N3 |
| version-00 Stage 7b | Config bundles on GCS + Pub/Sub reload, CI promotion, custom hostnames, scale-out, shared rate-limit store, Cloud SQL private IP | N5 |
| version-00 E1, E4, E5, E6 | Tenant app roles, certificates / federated credentials, Entra apps in Terraform, no Azure CLI pre-auth outside dev | N5 |
| version-00 Stage 8 | Antigravity OAuth sign-in (enterprise path); same-policy gate across surfaces | N6 (Gemini Enterprise part: deferred) |
| version-00 Stage 9 | SharePoint source, Office documents, chunking by definition, `inherit_from_source`, OBO, ADK evals in CI, retrieval ranking, OPA/Cedar, admin UI | N6 |
| version-00 Stage 3 | `sdlc-config explain` by UPN | N6 |
| version-00 E9 | Multi-tenant sign-in | Out of scope (unchanged) |
| version-01 §6 | Gemini Enterprise design, now with the A2A + A2UI path | N7 (agent side), §7 (deferred GE setup) |

## 10. Agent-generated UI (A2UI) and the A2A path for Gemini Enterprise (N7)

Explored and approved 2026-10-30. **Keep CopilotKit; make the agent GE-ready.**

### Findings
- **A2UI** ([a2ui.org](https://a2ui.org/); Google, Apache-2.0, CopilotKit contributes; spec v0.9.1 current, v1.0
  candidate; [`@a2ui/react`](https://github.com/a2ui-project/a2ui) 0.14.0): a declarative JSON format for
  agent-generated UI, limited to a **catalog** of approved components that client and agent both know. The client
  renders it with its own components and validates it; no executable code. **It is not a chat app**: renderers draw
  surfaces only. Its own ADK + AG-UI guide uses `ag_ui_adk` (what we run) with CopilotKit on the client
  (`@copilotkit/a2ui-renderer`) ([guide](https://a2ui.org/guides/a2ui-with-any-agent-framework/),
  [renderers](https://a2ui.org/reference/renderers/), [transports](https://a2ui.org/concepts/transports/),
  [catalogs](https://a2ui.org/concepts/catalogs/)).
- **Gemini Enterprise has its own UI with a built-in A2UI renderer** (standard components, A2UI v0.8 / v0.9, GE
  styling). Custom agents are registered as **A2A agents** (Cloud Run or Agent Runtime); A2UI travels as A2A
  `DataPart` (`application/json+a2ui`); GE sends its catalog per request; widget actions come back as the next turn
  ([register A2UI agents](https://docs.cloud.google.com/gemini/enterprise/docs/a2ui-agents/register-and-manage-an-a2ui-agent),
  [host on Cloud Run](https://docs.cloud.google.com/gemini/enterprise/docs/a2ui-agents/tutorial-host-agent-cloud-run),
  [Google Cloud blog](https://cloud.google.com/blog/topics/developers-practitioners/guide-to-gemini-enterprise-and-a2ui-integration)).
  Whether GE accepts components outside its own catalog is unclear.
- **GE auth fits our token path:** an A2A agent can carry an OAuth authorization; GE then sends the user's token in
  `Authorization: Bearer` ([register A2A agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-a2a-agent),
  Preview). For `.run.app` URLs GE also sends a Google OIDC token in `X-Serverless-Authorization` (consumed by Cloud
  Run; our services use `invoker_iam_disabled`, Entra stays the gate).
- **For GE the web front end is irrelevant:** neither CopilotKit nor an own chat client runs inside GE. What carries
  over is an **A2A endpoint** on the agent and the agent emitting **A2UI from the standard catalog**; the same A2UI
  renders in GE (A2A) and in `/chat/` (AG-UI + an A2UI renderer). Replacing CopilotKit: D6, not pursued.

### Work
1. **Spike first** (no product code until it passes):
   - how an ADK agent emits A2UI over AG-UI (`ag_ui_adk`) and over A2A from one code path;
   - whether the standard catalog can show our citation cards (title, link, source, lines/pages), the identity panel
     and connected-tool results;
   - an A2UI version accepted by both GE (v0.8 / v0.9) and `@copilotkit/a2ui-renderer`;
   - ADK's A2A server support with our ADK version, and how it fits behind `sdlc_web`'s middleware.
2. **A2UI output (after the spike):** produced **deterministically from MCP tool results** (citations, whoami,
   connected-tool results), never invented by the model for security-relevant data; standard catalog only; links
   `http(s)` only; A2UI user actions are input to the agent, **never authorization** (version-01 §3.2 item 5). The chat
   app renders A2UI with `@copilotkit/a2ui-renderer` (exact pin), replacing the hand-written renderers
   (`ui/copilotkit/components/renderers.tsx`) where the result is equivalent.
3. **A2A endpoint** on the agent service behind the same Entra middleware: user id = token `oid`, token only in the
   request context (never in session state), client state sanitised, one conversation = one session in the existing
   store (SQLite locally, Agent Engine on GCP). Reachable through oauth2-proxy locally; on GCP, how GE reaches it
   (direct to the agent with a Bearer token vs through oauth2-proxy) is decided in the spike.
4. **Tests and gate:** the same `search_knowledge` answer renders as citation cards in `/chat/` (AG-UI) and through a
   local A2A client (A2UI DataPart); the version-01 M5 security tests hold for the A2A endpoint (no token -> 401,
   another user's session refused, client state sanitised, no token in persisted events); CI runs the UI checks.

GE registration itself (OAuth authorization, GE app, Entra client) stays deferred (§7).

## 11. Chat UX (N8) — built 2026-10-30

**Status:** answer rendering is better (checked by the user, 2026-10-30). Still to check: `/` lands in `/chat/`,
the navbar user status, and the same on the tunnel and on GCP after `images` + `plan` + `apply`.

Requested 2026-10-30: chat answers looked unformatted (an extra blank line after every line), the app should open
on the chat after sign-in, and the navbar should show the signed-in user with the state of their PAT connections.

- **Answer formatting** (`ui/copilotkit`, `agents/bootstrap`):
  - CopilotKit renders answers as Markdown with Tailwind typography: 1.25em paragraph gaps and a 65ch width cap.
    When the model separates lines with blank lines, every line becomes a paragraph and looks double-spaced.
    `globals.css` tightens paragraphs, lists and headings for assistant messages only and uses the full column.
  - The agent instruction gained answer rules: short answer first, single blank lines between paragraphs only,
    lists / code fences / tables where they help, headings only for long answers, sources by title, no raw JSON.
  - Dark mode: CopilotKit's dark theme follows a `dark` class, our page follows the OS setting; a fixed inline
    script in `app/layout.tsx` sets the class from `prefers-color-scheme` (and follows changes).
- **`/` opens the chat:** `sdlc_web`'s middleware redirects `GET /` to `/chat/` when the chat app is on
  (`SDLC_AGUI_AGENT` set), after the token check. oauth2-proxy returns users to the page they asked for, so signing
  in at the bare URL lands in the chat. adk web stays at `/dev-ui/`.
- **Navbar user status** (`components/UserStatus.tsx`, `lib/status.ts`) on the chat and Connections pages:
  initials + name, one dot per connection (green connected, amber expiring within 14 days / expired / rejected by
  the provider, grey not connected), a panel with each connection's account and expiry, links to Connections and
  Sign out. Refreshes on focus and after a connect/disconnect.
  - `GET /me` (agent middleware): `{name, upn}` from the validated token only (no oid, groups or token),
    `Cache-Control: no-store`.
  - PAT status from the existing `GET /connections/` (MCP server; never returns tokens). Connections off (503) or a
    lapsed session (401): that part is hidden.
  - oauth2-proxy API routes gained `me\b` (compose and Terraform), so a lapsed session gets 401, not a login page.
- **Tests:** `tests/web/test_app.py` (`/me` fields and 401; `/` redirect only with the chat app on, still behind
  sign-in), `ui/copilotkit/tests/status.test.ts` (parsing, states, no token passthrough); typecheck and build.
- **To check (user):** local `docker compose up -d --build --wait`, then in the browser on localhost and the tunnel:
  `/` lands in `/chat/`, answers read normally (light and dark OS theme), the navbar shows your name and connection
  dots, connecting/disconnecting updates them. GCP: `images` + `plan` + `apply` (the API route change is in
  `run.tf`).

## 12. Per-source Entra groups (N9) — built 2026-11-02

**Why:** team membership comes from one Entra group per team, but readers of a source are often not a team. Each
source should be readable by its own Entra group, or by everyone, and `graph_query` should only walk those sources.

**As built:**
- `Source.access` takes `teams`, `roles`, `groups` (group aliases, e.g. one Entra group per source) and, new,
  `everyone: true` (schema, `SourceDef.access_everyone`, resolver reason `everyone <- sources/<id>.yaml#access/everyone`).
  Group grants already existed; they need no team.
- `graph_query` moved from `developer` to `viewer` (`eng-all`), so a source-group member without a team can call it.
  Not `eng-all → developer`: that would hand out `review_code`/`generate_tests` without the teams' repo limits.
- Classification is unchanged: the role ceiling still applies (a source group grants the source, not clearance).
- RLS was already per source (`documents`, `chunks`, `entities`, `mentions`, `edges`); graph joins by key happen at
  query time over RLS-visible rows only. No migration.
- Examples: `eng-standards` → `everyone: true`; `platform-infra` adds `groups: [infra-readers]`. Persona
  `infra-reader` (eng-all + infra-readers, no team) in the matrix; DB test `test_graph_query_for_a_source_group_member`.
- The git-ignored `config/env/{local,dev,staging}/groups.yaml` got an `infra-readers` placeholder ID that matches no
  group (fail closed), so config still validates.

**Open:**
- Create the `infra-readers` Entra group (admin action, needs confirmation), put its object ID in the git-ignored
  `groups.yaml` files, add a test user, then check `whoami(explain=true)` and `graph_query` on localhost and the tunnel.
- Many per-source groups raise the chance of group-claim overage: the Graph fallback (`identity.groups.overage_fallback`)
  covers it; for enterprise tenants, emit only "groups assigned to the application" to keep tokens small.

## 13. Direct members by email (N10) — built 2026-11-02

**Why:** the tenant has no strict Entra group per team or role, so group-based membership can't say who is in a team.
Admins need to add users directly, by their Entra email, to teams (with team roles) and to global roles.

**As built:**
- `config/env/<env>/users.yaml` (kind `UserMap`, `usermap.schema.json`, optional, git-ignored; `users.yaml.example`
  committed): `<alias>: { email, oid, teams: {<team>: [roles]}, roles: [...] }`. Who is in a team is tenant data (per
  env, like Entra group membership); what a team or role can do stays in committed config.
- Matching is on `oid` only (`UserMap.alias_for`); emails are never compared with token claims (they can change or be
  reused). An entry without an `oid` is "pending": validated, reported by `sdlc-config validate`, grants nothing.
- The loader turns entries into ordinary team membership entries and role bindings for `user:<alias>` (rules
  `env/<env>/users.yaml#users/<alias>/teams/<team>` and `.../roles`), so the resolver keeps one path; unknown teams or
  roles, duplicate emails or oids fail validation. `resolve(..., user=)`, `PolicyCache` keyed by the alias too.
  Team `membership` may now be empty (members only from users.yaml).
- MCP: `whoami` returns `user`; audit records carry `user_alias`; admin `config_explain(user=)` and `config_info`
  counts users/pending.
- CLI: `sdlc-config users sync --env <env> [--write] [--check]` (read-only `az ad user show`, prints the az account;
  `--write` saves oids, keeping the header comment only; `--check` reports renamed/deleted accounts);
  `explain --user <alias>`; personas take `user:`; `diff` copies the worktree users.yaml into revisions that know the kind.
- GCP: optional `users_yaml_path` (set by `gcp_deploy.ps1` when `config/env/<env>/users.yaml` exists) → secret
  `sdlc-<env>-users-yaml`, mounted into the MCP service only at `/app/config-users/` (Cloud Run: one secret per
  folder; `config/env/<env>/` already holds groups.yaml) with `SDLC_USERS_FILE` (loader path override; the file
  keeps its usual name in rules and bundles; `compile` ignores the override). `.dockerignore` keeps users.yaml out
  of images.
- Tests: `tests/config/test_users_config.py` (load, validation, resolution, pending, sync with a stubbed az),
  personas `direct-payments-dev`, `direct-viewer`, `pending-user` in the matrix, MCP tests (`whoami` by oid; the email
  claim alone grants nothing).

**Open:**
- GCP dev: run `gcp_deploy.ps1 -EnvName dev -Step plan` then `apply` with `config/env/dev/users.yaml` in place.
- Live check on localhost and the tunnel: a test user with no sdlc groups listed in `users.yaml` sees their team in
  `whoami(explain=true)`.

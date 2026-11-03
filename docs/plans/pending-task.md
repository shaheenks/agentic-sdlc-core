# Pending task — Agent runtimes: user, CI and ops agents

**Status:** pending, not scheduled (recorded 2026-11-03). Nothing here is built. Revisit when the trigger sources are
decided; then move it into a numbered plan (version-03) with milestones and exit gates.

Related: [version-02.md](version-02.md) (current plan; write tools = decision D5), [../ARCHITECTURE.md](../ARCHITECTURE.md)
§4–5 (request flow, identity model).

## 1. Goal

Three agent runtimes instead of one:

| Runtime | Agent | Serves | Identity on MCP calls |
|---|---|---|---|
| interactive | `user_agent` | People, in the chat app (renamed from `bootstrap`, 2026-11-03) | The signed-in user's Entra token (unchanged) |
| autonomous | `ci_agent` | Triggers from CI workflows (pull requests, failed builds) | Its own workload identity (Entra service principal) |
| autonomous | `ops_agent` | Triggers from operational alerts | Its own workload identity (Entra service principal) |

**Decided (2026-11-03):**
- Autonomous agents use their **own workload identity** (app-only tokens with an app role), never a user's token.
  A CI run can't securely carry the pusher's user token, and alerts have no user at all.
- First version is **read and report back**: read-only MCP tools, then post the result to where the trigger came
  from. No changes to other systems (write tools stay decision D5).

**Not decided:** which trigger sources come first (§5), report channels, and the other questions in §11.

## 2. What exists today

- One agent, [agents/user_agent/agent.py](../../agents/user_agent/agent.py) (renamed from `bootstrap`; the MCP server is now `mcp_servers/core_mcp`): ADK `Agent` + `McpToolset` with
  `agent_header_provider` (user token + conversation id), served by `libs/sdlc_web` (`create_app` →
  `get_fast_api_app(agents_dir=...)`) behind oauth2-proxy; `EntraUserBindingMiddleware` binds sessions to the token `oid`.
- The MCP token verifier (`sdlc_auth.entra.EntraTokenVerifier.load_access_token`) **rejects app-only tokens**
  (`idtyp == "app"` or no `scp`).
- Config already supports `app_role:` identities (roles.yaml bindings, team membership) and `Principal.app_roles`
  is already parsed, so the resolver needs no new identity kind for service principals.
- `sdlc_agent.with_team_context` fetches team instructions as the user; autonomous agents need a per-agent version.

## 3. Layout

```
agents/
  interactive/user_agent/      today's agents/user_agent, moved one level down; served by sdlc_web as now
  autonomous/ci_agent/         headless; served by the autonomous runtime
  autonomous/ops_agent/
libs/sdlc_runner/              autonomous runtime: trigger endpoints, queue, run loop, reporters
```

- Each runtime gets its own `agents_dir`, so the chat app can never load an autonomous agent and the autonomous
  runtime has no chat UI, no oauth2-proxy and no user sessions.
- Shared helpers stay in `libs/sdlc_agent` (instruction building, result formatting); prompts live with each agent.
- Open: one runtime service hosting both autonomous agents, or one service each (§11).

## 4. Identity (workload identity)

**Entra (admin action, needs confirmation):** one app registration / service principal per autonomous agent
(`sdlc-ci-agent`, `sdlc-ops-agent`), each assigned an app role on `sdlc-mcp` (`SDLC.Agent.CI`, `SDLC.Agent.Ops`).
Credentials are **federated** from the agent's GCP service account (no client secrets on GCP). Local dev may use a
dev-only secret or certificate in `.env` (must not leak into prod, as with other dev shortcuts).

**Agent → MCP:** an app-only token from client credentials, through a new `sdlc_auth` `service_header_provider`
(token cache, refresh before expiry, run id as `X-SDLC-Agent-Session`). User agents never get this path; autonomous
agents never get user tokens.

**MCP verifier:** accept an app-only token **only** if its `roles` contain an app role listed in config
(`platform.yaml identity.service_principals.allowed_app_roles`); tid, iss, aud, oid, signature and expiry checks stay;
the block list applies to service principal oids (kill switch). `Principal` gains `kind: user | service`.

**Config:**
- `roles.yaml`: bindings `app_role: SDLC.Agent.CI → ci-agent`, `app_role: SDLC.Agent.Ops → ops-agent`. Roles get
  read-only tools only (`list_skills`, `load_skill`, `get_agent_context`, `search_knowledge`, `graph_query`, review
  skills) and their own `max_classification`.
- Data: `Source.access.roles: [ci-agent]` / `[ops-agent]` per source, like any other grant.
- Team scoping for CI (which repos a run may look at): per-trigger constraints (§5) or `teams/<team>.yaml`
  `membership: app_role: ...`. Open (§11).
- Validation rule: a tool with `credentials.user` (users' own PAT connections) is never granted to a role bound
  to a service app role.
- Persona matrix: personas `ci-agent` and `ops-agent` (app roles only) with tool, skill and data rows.

**Audit:** records gain `principal_kind: service`, `app_id`, `trigger_id`, `run_id`; `agent_session_id` = run id.

## 5. Triggers (pluggable adapters; sources not decided)

```
caller ──► POST /triggers/<adapter> ──► verify caller ──► TriggerEvent ──► queue ──► agent run ──► reporter
                                      (per adapter)    (normalised)         202 + run id
```

- `TriggerEvent`: `kind` (ci | ops), adapter, source (repo / service), ref, a size-capped payload summary, event id,
  correlation id.
- Caller authentication per adapter; prefer OIDC over shared secrets:

  | Candidate source | Caller check |
  |---|---|
  | GitHub Actions | GitHub OIDC token: issuer, audience, `repository` / `workflow` claims checked against config |
  | Bitbucket Pipelines | Bitbucket OIDC token: issuer, audience, repository / workspace claims |
  | GCP Cloud Monitoring | Alert → Pub/Sub → authenticated push: Google-signed OIDC token from the expected service account |
  | Alertmanager, PagerDuty, others | Generic webhook with HMAC signature; secret via `sdlc_secrets` |

- New config kind **`Trigger`** (`config/triggers/<id>.yaml`): adapter, accepted callers (repos / workflows /
  service accounts), target agent, repo/service constraints, report channel, rate limit, dedupe window, `enabled`.
  Needs a JSON Schema, `_KINDS` registration, tests and a CODEOWNERS rule, like sources.
- Payloads are **untrusted input** (prompt injection): passed to the agent as data, size-capped, never used
  verbatim as tool arguments.

## 6. Execution model

- Asynchronous: the endpoint returns `202 + run id`; a queue (Cloud Tasks or Pub/Sub on GCP, in-process locally)
  starts one agent run per event.
- Idempotent by event id + dedupe window (CI retries, alert re-fires).
- Limits per run: timeout, maximum tool calls, model token budget; concurrency limit per agent.
- Sessions in the same store as the chat (SQLite locally, Agent Engine on GCP) with a short TTL; a run record
  (status, timings, outcome) for operators.

## 7. Reporting back (the only write in v1)

- One reporter per adapter: PR comment or check-run summary (CI), alert annotation or chat/webhook message (ops).
- Posting uses a **service credential scoped to reporting only** (e.g. a GitHub App with `pull_requests: write` /
  `checks: write`), referenced through `sdlc_secrets`, host in `knowledge.allowed_hosts`, sent through
  `sdlc_connectors.http.HttpClient`.
- Everything else stays read-only.

## 8. Security and guardrails

- Deny by default for service principals: only app roles listed in config are accepted, only bound roles' tools.
- No user connections (PATs) for autonomous agents; classification ceiling per agent role.
- Per-trigger repo/service constraints and rate limits; full audit of every run and tool call.
- Kill switch: block-list entry for the agent's service principal oid, or `Trigger.enabled: false`.
- Evals: prompt-injection payloads (malicious PR descriptions, alert text) must not change what the agent does.

## 9. Deployment

- Local: compose services `agent-ci`, `agent-ops` (profile `autonomous`, not started by `up`).
- GCP: Cloud Run service(s) with their own service accounts and federated Entra credentials; public ingress only
  for adapters that need it (GitHub/Bitbucket), Pub/Sub push otherwise. Terraform, run by the user.

## 10. Milestones (proposal)

| # | Scope | Exit gate |
|---|---|---|
| A1 | Identity: verifier accepts allowed app-only tokens, `Principal.kind`, config rules, `service_header_provider`, persona matrix | An app-only test token gets exactly the ci-agent role's tools and sources; an app token without an allowed role gets 401 |
| A2 | Autonomous runtime + first CI adapter + reporter; move `agents/user_agent` → `agents/interactive/user_agent` | A CI trigger produces a report on a test PR; audit shows the run end to end |
| A3 | First ops adapter + reporter | A test alert produces an annotation/message |
| A4 | GCP: services, federated credentials, Terraform | Both flows work on GCP dev |
| A5 | Guardrails and evals (injection, limits, dedupe) | Eval suite passes; limits enforced |

## 11. Open questions

1. Trigger sources for v1: GitHub Actions, Bitbucket Pipelines, GCP Cloud Monitoring (Pub/Sub), Alertmanager /
   PagerDuty webhooks?
2. Report channels: PR comments vs check runs; ops: alert annotation, Google Chat / Slack / Teams?
3. CI team scoping: map repo → team in the `Trigger`, or bind the CI app role into teams?
4. One autonomous runtime service or one per agent?
5. ~~Rename `bootstrap` to `user_agent`~~: done 2026-11-03 (with `mcp_servers/bootstrap` → `core_mcp`); see version-02 §14.
6. Write actions (open issues, re-run pipelines, roll back): decision D5; would need approval gates.

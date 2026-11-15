# GCP-native hosting

Status: proposed (2026-11-12). Decision D17 in [workflow-platform.md](workflow-platform.md). Plan: phase WN in
[version-04](../plans/version-04.md). Change records CH-0013 to CH-0017.

## 1. Why

GCP dev runs one Cloud Run service, `sdlc-app`, with three containers:
- oauth2-proxy, for Entra sign-in;
- the ADK agent behind `sdlc_web` (AG-UI, threads, A2A and session-ownership checks);
- the CopilotKit UI.

Next to it, `sdlc-mcp` is public and gated only by the Entra token. This design moves hosting to Google-native
services:
- IAP signs users in;
- the agent runs on Agent Runtime (Gemini Enterprise Agent Platform);
- Agent Registry catalogues the agent and the MCP server;
- Agent Gateway governs the traffic between them.

The knowledge backend does not change: Cloud SQL with pgvector and RLS, ingest jobs, config bundles and the
artifacts bucket.

## 2. Decisions (2026-11-12)

| # | Topic | Decision |
|---|---|---|
| N1 | Access control | **Layered.** Entra app-role RBAC stays the per-user authority in the MCP server (FR-AUTHZ, FR-IDN-002, team scoping, RLS). IAP, Cloud Run IAM and Agent Gateway add perimeter, agent and tool layers on top. |
| N2 | Identity at Google | Users are Cloud Identity accounts with Entra SSO; IAP admits them by a Cloud Identity group. |
| N3 | Rollout | A new environment `native` beside dev, in the same project. Dev keeps running until a cutover decision (CH-0017). |
| N4 | Local | Docker compose stays the local twin (oauth2-proxy, the agent in a container, `sdlc_web`). Only the hosting differs; agent and MCP code are shared. |
| N5 | MCP perimeter | Both tokens on every call to the MCP server: the Entra token in `Authorization` (read by the MCP code for per-user access), and the caller's Google ID token in `X-Serverless-Authorization` (checked by Cloud Run IAM before the request reaches the code). Chosen over a public service, where the gateway could be bypassed, and over internal ingress with Private Service Connect. |
| N6 | Agent entry point | A custom streaming method on Agent Runtime (`stream_query(message, session_id, user_token)`) so the token check and session ownership run before the agent. Alternatives for the session service are explored later. |

Rejected:
- **Gateway-only:** no per-user or per-team control and no per-user RLS.
- ~~Google identity end to end~~: rejected on 2026-11-12, adopted on 2026-11-14 (N7 to N12 below).

## 2a. Decisions (2026-11-14, revised 2026-11-15): two stacks, Google identity on the GCP one

On 2026-11-14 Entra group claims and Entra app roles were ruled out for the GCP-native system. On 2026-11-15 the
user chose to build it as a **second stack beside the existing one** instead of converting the existing one:

| | Entra stack (today, `dev`) | GCP stack (`native`) |
|---|---|---|
| Front end | `sdlc-app` on Cloud Run, oauth2-proxy (Entra) | `sdlc-ui-native` on Cloud Run, IAP (WN.4) |
| Agent | `user_agent` in the same container (`sdlc_web`) | `user_agent` on Agent Runtime (`runtime_app`) |
| MCP server | `core_mcp` | `core_mcp_gcp` |
| User token | Entra access token | Google ID token for our OAuth client |
| Membership | Entra app roles + `users.yaml` (by `oid`), CH-0011 | Google Groups + `users.yaml` (by email) |

Users are Cloud Identity accounts federated from Entra (SAML SSO), and the relevant Entra groups are synced to
Cloud Identity (assumed; the sync is the user's).

| # | Topic | Decision |
|---|---|---|
| N7 | User token (GCP stack) | The user's **Google ID token** whose audience is our own OAuth client, obtained by Google Identity Services in the browser (silent inside the IAP session) or an OAuth client flow (CLI, MCP clients). The agent forwards it in `Authorization` as the Entra stack forwards the Entra token. Rejected: forwarding the IAP JWT (audience is the UI, ~10 minutes, absent locally and for MCP clients). |
| N8 | Token validation | `core_mcp_gcp` and the Agent Runtime app verify it offline: Google's signing keys, issuer `https://accounts.google.com`, audience = the configured client ID(s), `email_verified`, `hd` = the configured Cloud Identity domain(s). The user id is `sub`. |
| N9 | Membership (GCP stack) | Google Groups named in config by **email address, committed in `config/`**, plus `users.yaml` matched on email, as a union. Entra app roles and the `groups`/`roles` claims play no part on this stack. |
| N10 | Group lookup | `core_mcp_gcp` asks the Cloud Identity Groups API on first use and caches the answer a few minutes; a failed lookup gives no group roles (fail closed). Designed for Cloud Identity Free: one direct-membership check per group in config (no nesting). On Premium, `searchTransitiveGroups` replaces it. The service account needs the Groups Reader admin role (user, Admin console). |
| N11 | Data | One knowledge backend for both stacks (sources, embeddings, graph, RLS ceilings: computed from roles, not from the identity). User-owned data (artifacts, connections, sessions) is kept apart by the id itself: an Entra `oid` is a GUID, a Google `sub` is 21 digits, so they cannot collide; the owner check accepts both shapes. Nothing is migrated or reset; each stack's users start with their own data. Audit records which stack wrote them. |
| N12 | Sign-in, local | The Entra stack is unchanged (CH-0011 holds for it). The GCP stack signs in with Google everywhere: IAP on `native`, and a compose profile `gcp` locally (oauth2-proxy with the Google provider in front of `sdlc_web` and `core_mcp_gcp`). Tests use a fake Google issuer. |
| N13 | One codebase, two entry points | `core_mcp` and `core_mcp_gcp` are thin components over one server library (`libs/sdlc_mcp`): the tools, audit, artifacts, connections and policy are shared; each component supplies only its **identity adapter** (token verifier, principal, membership source). Config is one catalog: a role or team binding may name an `app_role:` (read by the Entra stack) and a `group:` (read by the GCP stack); a parity check makes every persona resolve to the same roles on both. No server code is copied. |

Consequences:
- Workflow identities (FR-IDN-005) on the GCP stack are Google service accounts with their own ID token.
- External MCP clients and harnesses (FR-SURF-003, FR-SURF-004) keep using the Entra stack until the GCP stack has
  a Google OAuth path for them.
- The Agent Gateway egress list (CH-0018) swaps Entra's signing keys for Google's
  (`https://www.googleapis.com/oauth2/v3/certs`) when the engine moves to `core_mcp_gcp`.
- Cutover (CH-0017) becomes: move users to the GCP stack, then delete `core_mcp`, the `app_role:` bindings, the
  Entra adapter and oauth2-proxy. Until then, both stacks are tested on every change.

Rejected:
- Converting the Entra stack in place (the first 2026-11-14 draft): a big-bang identity switch with a data
  reset, and no way back.
- One `core_mcp` with an identity switch per deployment: the least code, but the GCP-only dependencies (Cloud
  Identity API) and its separate deploy are clearer as their own component; the shared library keeps the cost
  of the split small.

## 3. Architecture

```
browser ── IAP (Google account, Entra SSO) ──> sdlc-ui-native (Cloud Run, CopilotKit)
   │   Google Identity Services: the user's Google ID token for our OAuth client (same person as IAP)  [N7]
   ▼
sdlc-ui-native ── IAM (UI service account) ──> user_agent on Agent Runtime   (Google ID token passed per call)
                                                  │  egress via managed Agent Gateway (Agent Registry entry)
                                                  │  X-Serverless-Authorization: agent identity ID token (Cloud Run IAM)
                                                  │  Authorization: Bearer <user's Google ID token>
                                                  ▼
                                          sdlc-mcp-native (Cloud Run, IAM-only invoker)
                                                  │  Cloud Identity Groups API: the user's groups (cached)  [N10]
                                                  ▼
                                          Cloud SQL (RLS) · GCS · Secret Manager   (unchanged)
```

## 4. Access control layers

Each layer fails closed; a lower layer never widens what a higher one allows.

| Layer | Decided by | What |
|---|---|---|
| 1. Perimeter | IAP + a Cloud Identity group | Who can open the UI |
| 2. Identity binding | UI server | The Google ID token's user must be the IAP user, or the request is refused |
| 3. Agent → MCP | Cloud Run IAM + Agent Gateway (IAM Unified Access Policy, MCP tool allowlist) | Only `user_agent`'s identity reaches the MCP server, and only for catalog tools |
| 4. Per user | MCP server, `config/` | Google Groups and `users.yaml` (N9), team scoping, argument limits, rate limits, audit |
| 5. Data | Postgres RLS (unchanged) | Readable sources, per-source ceilings |

The gateway's tool allowlist is generated from `config/tools.yaml` (`sdlc-config gateway-policy`). Access stays
declared in `config/`, and the gateway never allows a tool that config does not have.

Calls stay "as the user" (NFR-SEC-006): the user's Google ID token (Entra token before N7) travels in `Authorization`, and the agent's
Google identity only proves which workload is calling, in `X-Serverless-Authorization`. Cloud Run checks that
header for IAM when it is present.

## 5. Components

- **MCP server** (`sdlc-mcp-native`, CH-0013): the existing image, with IAM-only invoker access. Config env
  `native`.
- **Agent** (`user_agent` on Agent Runtime, CH-0014): an Agent Runtime app wraps the existing `root_agent`.
  - It verifies the Entra token, takes `user_id` from the token's `oid`, refuses other users' sessions and
    sanitises client state. These are the rules `sdlc_web` applies today, moved into `sdlc_agent`.
  - Sessions live in Agent Runtime.
  - The agent identity is granted invoker on the MCP server.
- **Registry and gateway** (CH-0015): the agent and the MCP server are registered in Agent Registry. The managed
  egress gateway allows `user_agent` → `sdlc-mcp-native` only, with the tool allowlist; Model Armor is optional.
- **UI** (`sdlc-ui-native`, CH-0016):
  - the CopilotKit image with direct IAP on Cloud Run;
  - MSAL.js gets the Entra token silently, and the server checks it against the IAP user;
  - an AG-UI adapter calls Agent Runtime;
  - `/connections/` and `/artifacts/` are proxied by the UI server.
- **Hardening and cutover** (CH-0017): least-privilege service accounts, negative tests, CI deploy target and the
  cutover decision.

## 6. Status of the Google services (docs, 2026-11)

- **IAP directly on Cloud Run:** GA.
- **Agent Gateway:** managed for Agent Runtime, for both ingress and egress. For Cloud Run it is "coming soon";
  this design does not need it there.
- **Agent Registry:** Public Preview.
- **Agent Identity:** SPIFFE principals per agent. There is no documented forwarding of the user's credential to
  a downstream MCP server, so our own token passthrough stays.
- **In `sdlc-demo-env01` (WN.0, 2026-11-12):**
  - the IAP, Agent Registry, Agent Identity (and credentials), network services and Model Armor APIs are enabled
    by Terraform (`agent_platform_apis`);
  - `gcloud` 586 has `agent-registry` (services, agents, mcp-servers, endpoints, bindings), `agent-identity`
    (auth-providers) and `network-services agent-gateways` (import, export from YAML); all answer in
    `asia-southeast1`, with no resources yet;
  - the Terraform provider (google 7.46.1) has `google_network_services_agent_gateway`,
    `google_agent_registry_service`, `_agent`, `_mcp_server`, `_endpoint` and `_binding`,
    `google_vertex_ai_reasoning_engine`, Cloud Run `iap_enabled` and `google_iap_web_cloud_run_service_iam_member`,
    so every piece can be Terraform;
  - confirmed live (2026-11-13, CH-0014): the custom `stream_query` streams through Agent Runtime, and the agent
    identity mints a Google ID token that Cloud Run IAM accepts; `sdlc-mcp-native` audited the agent's tool calls
    as the user (`whoami`, `list_skills`, `get_agent_context`: allowed, the user's team, with the conversation id);
  - confirmed live (2026-11-13, CH-0015): with the engine attached to the Agent Gateway, IAP authorized each
    request (`egressViaIAP` granted, DRY_RUN) and `sdlc-mcp-native` audited the calls as the user, so the gateway
    passes both `Authorization` and `X-Serverless-Authorization` unchanged;
  - confirmed live (2026-11-13, enforced, CH-0018): with the IAP check failing closed, the agent answers and every
    gateway decision for `sdlc-mcp-native` is granted. The first enforce attempt showed that the agent's other
    destinations (Entra keys, Gemini, sessions) must be registered endpoints too;
  - still to check live: MSAL silent SSO under IAP (WN.4).

## 7. Risks

- Preview services may change; the WN.0 spike confirms each one before WN.1.
- The gateway might not keep both auth headers. The fallback is a signed user assertion from the agent; it changes
  NFR-SEC-006 and needs its own decision.
- Two silent sign-ins (IAP and MSAL) add a token round trip per session.
- External MCP clients (Antigravity) and A2A clients cannot reach the IAM-only MCP server; they stay on dev until
  W6.

Sources:
- [Agent Gateway overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview)
- [Agent Identity](https://docs.cloud.google.com/agent-builder/agent-engine/agent-identity)
- [Agent Platform overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/overview)
- [IAP with Cloud Run](https://cloud.google.com/blog/products/serverless/iap-integration-with-cloud-run)
- [Authenticate MCP servers on Cloud Run](https://docs.cloud.google.com/run/docs/ai/authenticate-mcp-servers)

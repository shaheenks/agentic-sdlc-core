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

Rejected for now:
- **Google identity end to end:** the MCP server would trust Google tokens, and membership would come from Cloud
  Identity groups. That brings back group lookups, which CH-0011 removed.
- **Gateway-only:** no per-user or per-team control and no per-user RLS.

## 3. Architecture

```
browser ── IAP (Google account, Entra SSO) ──> sdlc-ui-native (Cloud Run, CopilotKit)
   │   MSAL silent SSO: Entra token for api://sdlc-mcp/access_as_user (same person as IAP)
   ▼
sdlc-ui-native ── IAM (UI service account) ──> user_agent on Agent Runtime   (Entra token passed per call)
                                                  │  egress via managed Agent Gateway (Agent Registry entry)
                                                  │  X-Serverless-Authorization: agent identity ID token (Cloud Run IAM)
                                                  │  Authorization: Bearer <user's Entra token>
                                                  ▼
                                          sdlc-mcp-native (Cloud Run, IAM-only invoker)
                                                  ▼
                                          Cloud SQL (RLS) · GCS · Secret Manager   (unchanged)
```

## 4. Access control layers

Each layer fails closed; a lower layer never widens what a higher one allows.

| Layer | Decided by | What |
|---|---|---|
| 1. Perimeter | IAP + a Cloud Identity group (mirrors `SDLC.User`) | Who can open the UI |
| 2. Identity binding | UI server | The Entra token's user must be the IAP user, or the request is refused |
| 3. Agent → MCP | Cloud Run IAM + Agent Gateway (IAM Unified Access Policy, MCP tool allowlist) | Only `user_agent`'s identity reaches the MCP server, and only for catalog tools |
| 4. Per user | MCP server, `config/` (unchanged) | App roles, team scoping, argument limits, rate limits, audit |
| 5. Data | Postgres RLS (unchanged) | Readable sources, per-source ceilings |

The gateway's tool allowlist is generated from `config/tools.yaml` (`sdlc-config gateway-policy`). Access stays
declared in `config/`, and the gateway never allows a tool that config does not have.

Calls stay "as the user" (NFR-SEC-006): the user's Entra token travels in `Authorization`, and the agent's
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
  - still to check live, with test resources: the gateway passing both auth headers, streaming from the custom
    method, and MSAL silent SSO under IAP. Each is checked in the phase that builds it (WN.2, WN.3, WN.4).

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

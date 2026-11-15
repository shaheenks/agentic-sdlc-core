# Change log

## 2026-11-15

- **Update**: CH-0022 done (WG.2): new component `core_mcp_gcp` (the GCP stack's MCP server); the agent's
  entry checks take the stack's verifier (`SDLC_IDENTITY_PROVIDER`); migration 009 lets an artifact owner be a
  Google `sub`; `sdlc-mcp-native` runs `core-mcp-gcp` as its own service account; gateway egress to Google's
  keys; compose profiles `gcp` and `gcp-tunnel`; `google_id_token.py`; guide `docs/guides/GCP_STACK.md`. Five
  requirements reworded per stack and back to `draft`. Live check pending the user's rollout.
- **Fix**: CH-0022: the first dev apply failed (`sdlc-mcp-native` startup probe: `ENTRA_TENANT_ID is not set`);
  the config loader leaves the Entra fields unused on the GCP stack (`SDLC_IDENTITY_PROVIDER=google`).
- **Update**: CH-0021 follow-up: the user created the Cloud Identity groups and set `identity.google`; the repo
  config binds a `group:` beside every `app_role:`, the personas use the real groups and `validate` now runs
  the stack parity check on the repo config (passes).
- **Update**: CH-0021 done (WG.1): Google ID token verifier, Cloud Identity group directory (direct mode, as the
  user confirmed Cloud Identity Free; transitive for Premium) and the Google identity adapter in `sdlc_auth`;
  `group:` bindings beside `app_role:`, `identity.google`, `users.yaml` by email on the GCP stack and the persona
  parity check in `sdlc_config`. Ten requirements reworded per stack and back to `draft`; the configuration,
  security and tenants rule sets and `CLAUDE.md` allow committed Google group emails. The repo config binds no
  group until the user gives the emails.
- **Update**: CH-0020 done (WG.0, refactor): the MCP server body moved to the new library `libs/sdlc_mcp` behind an
  `IdentityAdapter`; `core_mcp` is now the Entra adapter and entry point only, with no change in behaviour. New
  component concept `sdlc_mcp`; the requirement trace is split between `sdlc_mcp` and `core_mcp`.
- **Update**: architecture change: the GCP-native system becomes a second stack with Google identity (design
  decisions N7 to N13): IAP UI, the agent on Agent Runtime and a new MCP server `core_mcp_gcp` with Google Groups
  and `users.yaml`; the Entra stack on `dev` stays as it is, sharing one server library, config catalog and
  knowledge backend. The user approved CH-0020 (server library), CH-0021 (Google identity and groups) and CH-0022
  (`core_mcp_gcp` and the GCP stack), recorded by Claude on the user's instruction. Plan phase WG before WN.4.

## 2026-11-13

- **Update**: Agent Gateway enforced on GCP dev (CH-0015, CH-0018): the IAP check fails closed and the agent still
  answers through the gateway; no denials in the audit log.
- **Update**: enforcing the Agent Gateway on dev denied the agent's fetch of Entra's signing keys
  (`unregisteredEndpoint`), so every call failed closed; dev is back in DRY_RUN. The user approved CH-0018 and CH-0019
  (recorded by Claude on the user's instruction). CH-0018 done: the agent's other destinations (Entra keys, Gemini,
  sessions) are registered endpoints with their own `roles/iap.egressor` grants. CH-0019 done: the Agent Runtime
  methods return refusals as results, so the user's token is never echoed into errors or logs. Apply, engine
  redeploy and enforcement are the user's.
- **Update**: CH-0015 live on GCP dev in DRY_RUN: the agent's MCP traffic goes through the Agent Gateway, IAP grants each
  request, and both auth headers reach `sdlc-mcp-native` unchanged (WN.0 item confirmed).
- **Update**: CH-0015 fix: the gateway's authorization policy needs the Network Security API; added to the Agent Platform
  APIs, and the extension and policy now wait for the APIs.
- **Update**: CH-0015 fix: the IAP authz extension needs `iapPolicyVersion` (apply failed with 400); set to `V1`, which
  evaluates the agent's IAM allow binding. V2 (Unified Access Policy) is a follow-up.
- **Update**: the user approved CH-0015 and NFR-SEC-015 (recorded by Claude on the user's instruction). CH-0015 done:
  Agent Gateway, the registry entry for `sdlc-mcp-native`, the IAP check (starting in DRY_RUN) and the agent's
  tool-scoped grant, all in Terraform; the allowlist is generated from `tools.yaml` by `sdlc-config gateway-policy`.
  NFR-SEC-015 `built`. Apply, engine redeploy and enforcement are the user's.
- **Update**: the user agent runs on Agent Runtime on GCP dev (CH-0014 live): the user's token is accepted, the answer streams,
  and `sdlc-mcp-native` audits the agent's tool calls as the user through Cloud Run IAM. WN.0 items for streaming and
  the agent identity confirmed.
- **Update**: CH-0014 fixes from the first live run on Agent Runtime (the user's token was accepted and the session created):
  every MCP client in the agent now uses `sdlc_auth.adk.mcp_headers` (the team-context call had no Cloud Run IAM header
  and got 401); the MCP connection timeout is 30 s (`SDLC_MCP_TIMEOUT`, cold starts); Gemini uses
  `SDLC_MODEL_LOCATION` (`global`) while sessions stay in the engine's region (the model call got 404).
## 2026-11-12

- **Update**: CH-0014 fix: `deploy_agent_runtime.py` passes the `class_methods` a source deploy needs (generated by the SDK from
  the staged app) and packs the source packages from the staged folder, so `user_agent/` is at the archive's top level.
  `--dry-run` now checks both without calling the API.
- **Update**: the user approved CH-0014 (recorded by Claude on the user's instruction). CH-0014 done: the user agent's Agent
  Runtime app with the shared runtime guard, the Cloud Run IAM header, `deploy_agent_runtime.py` and the invoker grant
  on `sdlc-mcp-native`. NFR-PORT-003 edited, back to `draft`. Deploy and apply are the user's.
- **Update**: the user approved CH-0013 (recorded by Claude on the user's instruction). CH-0013 done: `sdlc-mcp-native` (invoker
  IAM on) next to `sdlc-mcp-dev`, sharing its backend and config, behind `native_enabled`. NFR-SEC-010 edited, back to
  `draft`. GCP dev needs plan + apply (user).
- **Update**: WN.0 read-only spike: the Agent Platform APIs are enabled in GCP dev (user applied Terraform); gcloud and the
  Terraform provider support Agent Registry, Agent Gateway, Agent Runtime and IAP on Cloud Run, so CH-0015 uses
  Terraform instead of scripts. Live checks move into the phases that build each part.
- **Update**: GCP-native design decisions N5 (Entra token and Cloud Run IAM token both on MCP calls) and N6 (custom
  streaming method on Agent Runtime; session service alternatives later). infra/gcp enables the Agent Platform APIs
  behind `agent_platform_apis` (on in dev) for the WN.0 spike.
- **Creation**: design `docs/designs/gcp-native-hosting.md` (decision D17, plan phase WN) and change records CH-0013 to
  CH-0017 (`draft`): IAP, the user agent on Agent Runtime, the MCP server on Cloud Run with IAM-only access, Agent
  Registry and Agent Gateway, in a new `native` environment. New draft NFR-SEC-015 (layered access control).
- **Update**: the user approved CH-0004 with a cap of 10 versions (recorded by Claude on the user's instruction). CH-0004
  done: 50 documents per user (a document counts once) and 10 versions per document. FR-ART-001 and FR-ART-002 edited
  and back to `draft`.
- **Update**: the user approved CH-0007 and NFR-MAINT-005 (recorded by Claude on the user's instruction). CH-0007 done:
  `okf_bundle.py` has tests (`tests/knowledge`), the lint rejects a `verified_by` that is not a test and a code-backed
  requirement whose criteria are `to be defined`, and pytest runs the lint on the real bundle. NFR-MAINT-005 `live`.
- **Update**: the user switched the Entra tenant to app roles only (new roles assigned, old roles, groups claim,
  groups and the Graph secret removed) and deployed CH-0003, CH-0009, CH-0011 and CH-0012 to GCP dev (images, db,
  config, plan + apply). FR-AUTHZ-006 stays `built` until its live check.

## 2026-11-11

- **Update**: the user approved CH-0001, CH-0002, FR-KNOW-006, FR-KNOW-007 and FR-CONN-003 (recorded by Claude on the
  user's instruction).
- **Update**: CH-0001 done. FR-KNOW-006, FR-KNOW-007 and FR-CONN-003 are `built`, satisfied by ingest_loaders,
  sdlc_connectors, ingest_bootstrap, core_mcp and config. FR-KNOW-001, FR-KNOW-004 and FR-CONN-002 lose the split-out
  parts and are back to `draft`. Version-03 P8 names the three requirements as its live-check targets.
- **Update**: CH-0002 done. FR-AUTHZ-001, FR-AUTHZ-002, FR-AUTHZ-005, FR-SURF-002, NFR-REL-001 and NFR-SEC-004 drop
  criteria that NFR-MAINT-002, NFR-MAINT-004, NFR-SEC-002, NFR-SEC-009, FR-CFG-003 and FR-IDN-002 already state, and
  are back to `draft`.
- **Update**: the user re-reviewed and approved the nine requirements edited by CH-0001 and CH-0002: FR-KNOW-001,
  FR-KNOW-004, FR-CONN-002, FR-AUTHZ-001, FR-AUTHZ-002, FR-AUTHZ-005, FR-SURF-002, NFR-REL-001 and NFR-SEC-004 are
  `stable` again (recorded by Claude on the user's instruction).
- **Update**: the user approved CH-0006 (recorded by Claude on the user's instruction). CH-0006 done: offline tests
  `tests/infra/test_compose.py`, `test_workspace.py`, `test_terraform.py` (new dev dependency `python-hcl2`) and
  `tests/agent/test_user_agent.py` now verify compose, workspace, infra_gcp and user_agent. infra_gcp is no longer
  verified by a workflow file.
- **Deprecation**: the user approved CH-0003 (recorded by Claude on the user's instruction). CH-0003 done: `review_code`,
  `generate_tests` and `approve_design` removed from the code, `tools.yaml`, `roles.yaml`, the team files and the
  persona matrix; FR-ACT-001 `deprecated` and `parked`. Policy tests use two fixture-only tools. GCP dev needs
  `-Step images` and `-Step config` together.
- **Update**: the user approved CH-0009 and CH-0011 (recorded by Claude on the user's instruction). CH-0009 done: team
  roles renamed to `member` and `approver` (app roles `SDLC.<Team>.Member|Approver`) and scoped to their team, which
  closes the cross-team leak. The classification ceiling is per source; migration 008 checks each row against its own
  source's ceiling. FR-AUTHZ-006 is `built`. GCP dev needs the Entra app-role switch with `-Step images`, `-Step db`
  and `-Step config` in one window.
- **Update**: CH-0011 done: Entra groups and the group map are gone; membership comes from app roles and users.yaml only.
  FR-IDN-002, FR-AUTHZ-005, FR-CFG-002, FR-IDN-003, NFR-PORT-001, NFR-PRIV-003 and NFR-SEC-004 edited and back to
  `draft`; the seven rule sets edited and back to `draft`. Team `owners` are GitHub handles that CODEOWNERS must
  match. CH-0005 dropped (superseded). Follow-up: remove the unused groups and Graph secrets from infra/gcp.
- **Update**: the user removed the Entra groups and deployed CH-0009/CH-0011 to GCP dev (images, db, config). The user
  approved CH-0012 (recorded by Claude on the user's instruction). CH-0012 done: infra/gcp no longer creates, grants
  or mounts the `groups-yaml` and `entra-graph-secret` secrets; `gcp_deploy.ps1` no longer needs `groups.yaml`. GCP dev
  needs `-Step plan` + `apply` (user).

- **Creation**: NFR-OPS-002 continuous deployment to GCP dev (`draft`) and change record CH-0010: a GitHub workflow (bash on
  Linux runners) deploys every merge to `main`, running only the steps the changes need, in order. `gcp_deploy.ps1`
  stays for Windows next to a new `gcp_deploy.sh`; both read one manifest and a parity test keeps them equal. NFR-MAINT-003
  edited to scope "no secrets" to the `ci` checks; back to `draft`.
- **Creation**: change record CH-0011 (`draft`): membership from app roles only. It drops Entra groups and the group map,
  supersedes CH-0005, and lists seven requirement edits to apply on approval. Team `owners` become the GitHub handles
  that CODEOWNERS lists (design D15).

- **Creation**: change record CH-0008 (`draft`), the workflow platform design baseline, and the target design
  `docs/designs/workflow-platform.md`. Added 15 draft requirements: FR-WFL-001 to FR-WFL-006, FR-IDN-005,
  FR-SURF-004, FR-KNOW-008 to FR-KNOW-010, FR-CONV-002, NFR-REL-005, NFR-SEC-012 and NFR-SEC-013.
- **Update**: FR-AUTHZ-003 (platform and team roles), NFR-SEC-001 (event services, agent gateway) and NFR-QUAL-001
  (eval covers every content type) edited; back to `draft`.
- **Deprecation**: FR-AUTO-001, replaced by the FR-WFL requirements and FR-IDN-005.
- **Update**: system context rewritten around the workflow classes, and conventions gain the `WFL` area; both back to
  `draft`.
- **Update**: design decisions D1 to D7 applied:
  - roles: platform `viewer` and `admin`; team `member` and optional `approver`, scoped to their team (new
    FR-AUTHZ-006);
  - ops findings go to Jira or an admin alert;
  - the coding agent is built on Google ADK;
  - Kubernetes and Splunk push;
  - third-party agents use A2A with the user token (FR-SURF-002 back to `draft`);
  - the Agent Gateway is optional;
  - memory is parked (FR-CONV-002 `parked`).
- **Creation**: change record CH-0009 (`draft`): rename the team roles and fix the cross-team role leak.
- **Update**: design decisions D10 and D11 recorded:
  - MCP backends can be segregated per workflow (new NFR-SEC-014);
  - autonomous workflows use server-side service connections, initially broad-scoped Jira, Confluence and Bitbucket
    tokens (new FR-CONN-004);
  - NFR-SEC-012 now keeps every external credential out of the sandbox (the runtime pushes the patch);
  - NFR-SEC-013 now covers all external-system credentials.
- **Update**: design decisions D8, D9 and D12 recorded:
  - each team's Jira project for ops findings is declared in its team configuration (FR-WFL-005);
  - the role rename switches the Entra app roles in one step (CH-0009);
  - one set of service tokens per workflow (FR-CONN-004).

- **Update**: design decision D13 recorded: admin alerts go to a Jira queue or an email message, declared in
  platform configuration (FR-WFL-005). No design questions are open.

## 2026-11-10

- **Creation**: change records CH-0001 to CH-0007 (`draft`, awaiting review), from a review of the
  requirements and design: built vs live split, one owner per criterion, retire the SDLC action
  stubs, artifact version limit, remove the Graph overage fallback, tests for unverified
  components, checks for the specification tooling. New draft requirements FR-KNOW-006,
  FR-KNOW-007, FR-CONN-003 and NFR-MAINT-005.
- **Creation**: bundle scaffold (OKF 0.2), [conventions](conventions.md) and the
  `scripts/okf_bundle.py` lint and index tool.
- **Creation**: [system context](system/context.md), 36 functional and 32 non-functional
  requirements, drafted from `docs/FEATURE_INVENTORY.md`, `docs/ARCHITECTURE.md`, `CLAUDE.md` and
  `docs/plans/version-03.md`.
- **Update**: all 68 requirements reviewed and accepted; they are now `stable`.
- **Creation**: component register (22 components, accepted as a first version: `stable`) with `satisfies` and
  `verified_by` trace keys, and the generated [traceability matrix](traceability.md).
- **Update**: CI job `knowledge` runs the bundle lint; pull requests get a drift hint.
- **Update**: change records (`changes/CH-<nnnn>.md`) defined in the conventions and checked by the
  lint; working rules added to `CLAUDE.md`. No existing work is backfilled.
- **Creation**: seven rule sets in `rules/`, moved word for word from `CLAUDE.md`, which now keeps
  the always-apply rules and a routing table. Requirement sources point at the rule sets.
- **Update**: system context, conventions and the seven rule sets reviewed and accepted (`stable`).

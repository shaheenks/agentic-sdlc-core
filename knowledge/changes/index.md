# Changes

## Done

- [CH-0001: Separate built capabilities from live ones](CH-0001.md) - Parts of three live requirements that were built but never checked against a real system become their own built requirements, so the matrix shows what P8 still has to check.
- [CH-0002: State each acceptance criterion once](CH-0002.md) - Six requirements drop criteria that another requirement already states, so each fact has one owner and one place to change.
- [CH-0003: Retire the SDLC action stubs](CH-0003.md) - review_code, generate_tests and approve_design only echo their input; they are removed from the catalog, the roles, the teams and the code, and FR-ACT-001 is retired.
- [CH-0004: Count documents, not versions, against the artifact limit](CH-0004.md) - The 50-per-user limit counts documents (stable ids); each document keeps at most 10 versions.
- [CH-0006: Test the components that have no automated verification](CH-0006.md) - Offline tests for compose, the workspace, user_agent and infra_gcp, so their trace claims are checked on every run.
- [CH-0007: Check the specification tooling](CH-0007.md) - The bundle's own tooling gets a requirement, stricter lint rules and its own tests.
- [CH-0009: Rename team roles and scope them to their team](CH-0009.md) - The team roles developer and lead become member and approver, and a team role grants access only within its own team, which closes today's cross-team leak.
- [CH-0011: Membership from app roles only](CH-0011.md) - Entra groups are dropped from the access model; platform, team and workflow roles come only from Entra app roles (plus direct members), so no group IDs or group map exist anywhere.
- [CH-0012: Remove the group map and Graph secrets from GCP](CH-0012.md) - Terraform stops creating, granting and mounting the unused groups-yaml and entra-graph-secret secrets, and the deploy script stops requiring groups.yaml.
- [CH-0013: MCP server on Cloud Run with IAM-only access (native env)](CH-0013.md) - A new environment `native` runs the existing MCP server as a Cloud Run service that only allowed Google identities can invoke; the Entra token keeps deciding per-user access.
- [CH-0014: User agent on Agent Runtime](CH-0014.md) - The existing user agent is deployed to Agent Runtime behind a wrapper that verifies the user's Entra token, owns sessions per user and forwards the token to the MCP server with the agent's identity.
- [CH-0015: Agent Registry and Agent Gateway for the native stack](CH-0015.md) - The agent and MCP server are registered in Agent Registry, and the managed Agent Gateway allows only the user agent to reach the MCP server, for the tools config declares.
- [CH-0016: Chat UI on Cloud Run behind IAP](CH-0016.md) - The CopilotKit UI runs on Cloud Run behind IAP, gets the user's own Google ID token with a server-side sign-in bound to the IAP user, and talks to the agent on Agent Runtime and to sdlc-mcp-native.
- [CH-0018: Register the agent's other egress destinations in Agent Registry](CH-0018.md) - Entra's signing keys, Gemini and Agent Runtime sessions become registered endpoints the agent is granted, so the Agent Gateway can enforce without denying the agent's own work.
- [CH-0019: Agent Runtime methods return errors instead of raising them](CH-0019.md) - The runtime app's methods report refusals as error results, so Agent Runtime never echoes the request, and with it the user's token, into its error message and logs.
- [CH-0020: The MCP server body becomes a library with an identity adapter](CH-0020.md) - The tools, audit, artifacts, connections and policy wiring of core_mcp move into libs/sdlc_mcp behind an identity adapter port, so a second server (core_mcp_gcp) can reuse them; core_mcp becomes the Entra entry point with no change in behaviour.
- [CH-0021: Google identity and Google Groups membership for the GCP stack](CH-0021.md) - The libraries gain a Google ID token verifier, a Cloud Identity group directory and group bindings in config beside app-role bindings, with a parity check that every persona resolves the same on both stacks.
- [CH-0022: core_mcp_gcp and the GCP stack on Google identity](CH-0022.md) - A new MCP server component core_mcp_gcp (Google adapter) replaces core_mcp behind sdlc-mcp-native; the agent on Agent Runtime verifies Google ID tokens; the gateway, database owner check, compose and scripts follow. The Entra stack is unchanged.
- [CH-0025: Runtime refusals use a key the client library does not reserve](CH-0025.md) - The Agent Runtime app reports refusals under a "refusal" key instead of "error", because google.genai takes any streamed chunk starting with an "error" key for an API error and crashes on the string code.

## Dropped

- [CH-0005: Remove the Graph group-overage fallback](CH-0005.md) - The switched-off Microsoft Graph lookup for users with too many groups is removed from the sign-in path, with its config keys, secret and Graph host.

## Open

- [CH-0008: Workflow platform design baseline](CH-0008.md) - The finalized POC design becomes the specification. There are four workflow classes, event intake, enrichment and delivery, workflow identity, team-scoped platform and team roles, a sandboxed ADK implementation agent, harness catalogs and knowledge extensions.
- [CH-0010: Continuous deployment to GCP dev](CH-0010.md) - A GitHub workflow deploys every merge to main to GCP dev, running only the deployment steps the changes need, in a fixed order.
- [CH-0017: Native stack hardening, CI target and cutover decision](CH-0017.md) - Least-privilege identities and negative tests for the native stack, the CI deploy target for it, and the decision whether users move from dev to native.
- [CH-0023: Faster test suite](CH-0023.md) - Shared fixtures for the parts of test setup that never change (signing key, config snapshot, read-only MCP servers), a slow marker for the inner loop, and parallel runs, so the suite gives the same results in about half the time.
- [CH-0024: Image tags from build inputs](CH-0024.md) - Each image is tagged with a hash of its own build inputs, so gcp_deploy.ps1 builds and pushes only images whose inputs changed and Terraform rolls out only services whose image changed.

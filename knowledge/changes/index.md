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

## Dropped

- [CH-0005: Remove the Graph group-overage fallback](CH-0005.md) - The switched-off Microsoft Graph lookup for users with too many groups is removed from the sign-in path, with its config keys, secret and Graph host.

## Open

- [CH-0008: Workflow platform design baseline](CH-0008.md) - The finalized POC design becomes the specification. There are four workflow classes, event intake, enrichment and delivery, workflow identity, team-scoped platform and team roles, a sandboxed ADK implementation agent, harness catalogs and knowledge extensions.
- [CH-0010: Continuous deployment to GCP dev](CH-0010.md) - A GitHub workflow deploys every merge to main to GCP dev, running only the deployment steps the changes need, in a fixed order.
- [CH-0016: Chat UI on Cloud Run behind IAP](CH-0016.md) - The CopilotKit UI runs on Cloud Run with IAP sign-in, gets the user's Entra token by silent SSO, checks it matches the IAP user, and talks to the agent on Agent Runtime.
- [CH-0017: Native stack hardening, CI target and cutover decision](CH-0017.md) - Least-privilege identities and negative tests for the native stack, the CI deploy target for it, and the decision whether users move from dev to native.

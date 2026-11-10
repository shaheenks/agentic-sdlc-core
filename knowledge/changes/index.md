# Changes

## Open

- [CH-0001: Separate built capabilities from live ones](CH-0001.md) - Parts of three live requirements that were built but never checked against a real system become their own built requirements, so the matrix shows what P8 still has to check.
- [CH-0002: State each acceptance criterion once](CH-0002.md) - Six requirements drop criteria that another requirement already states, so each fact has one owner and one place to change.
- [CH-0003: Retire the SDLC action stubs](CH-0003.md) - review_code, generate_tests and approve_design only echo their input; they are removed from the catalog, the roles, the teams and the code, and FR-ACT-001 is retired.
- [CH-0004: Count documents, not versions, against the artifact limit](CH-0004.md) - The 50-per-user limit counts documents (stable ids); each document keeps at most 20 versions.
- [CH-0005: Remove the Graph group-overage fallback](CH-0005.md) - The switched-off Microsoft Graph lookup for users with too many groups is removed from the sign-in path, with its config keys, secret and Graph host.
- [CH-0006: Test the components that have no automated verification](CH-0006.md) - Offline tests for compose, the workspace, user_agent and infra_gcp, so their trace claims are checked on every run.
- [CH-0007: Check the specification tooling](CH-0007.md) - The bundle's own tooling gets a requirement, stricter lint rules and its own tests.
- [CH-0008: Workflow platform design baseline](CH-0008.md) - The finalized POC design becomes the specification. There are four workflow classes, event intake, enrichment and delivery, workflow identity, team-scoped platform and team roles, a sandboxed ADK implementation agent, harness catalogs and knowledge extensions.
- [CH-0009: Rename team roles and scope them to their team](CH-0009.md) - The team roles developer and lead become member and approver, and a team role grants access only within its own team, which closes today's cross-team leak.

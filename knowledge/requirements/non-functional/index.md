# Non-functional

## Auditability

- [NFR-AUD-001: Every decision is audited](NFR-AUD-001.md) - Each authorization decision and data access produces one structured audit record.
- [NFR-AUD-002: Records can be correlated](NFR-AUD-002.md) - Audit records link to the request, conversation, trace and configuration version.

## Maintainability

- [NFR-MAINT-001: Modular workspace](NFR-MAINT-001.md) - Components are siblings in one workspace and shared code lives only in libraries.
- [NFR-MAINT-002: Access rules are covered by tests](NFR-MAINT-002.md) - A new tool, source or team cannot be added without the tests that pin its access.
- [NFR-MAINT-003: CI runs without secrets](NFR-MAINT-003.md) - The full CI suite runs with no secrets and no cloud calls.
- [NFR-MAINT-004: Permission changes are reviewable](NFR-MAINT-004.md) - Every configuration change shows its effect on each persona before merge.
- [NFR-MAINT-005: The specification is traced and checked](NFR-MAINT-005.md) - Every built requirement traces to components and every component to tests, and a tool checks the trace on every change.

## Observability

- [NFR-OBS-001: End-to-end tracing](NFR-OBS-001.md) - One agent turn is one trace across the agent, the MCP server and Postgres.

## Operability

- [NFR-OPS-001: Production operations](NFR-OPS-001.md) - Custom hostnames, pipeline deploys, private database networking and alerting.

## Portability

- [NFR-PORT-001: Tenant-agnostic identity](NFR-PORT-001.md) - The platform can be pointed at another Entra tenant by configuration alone.
- [NFR-PORT-002: Configurable endpoints](NFR-PORT-002.md) - Hostnames and public URLs are configuration; development works on localhost and through the tunnel.
- [NFR-PORT-003: Local and cloud parity](NFR-PORT-003.md) - The same components run under Docker Compose locally and on GCP.
- [NFR-PORT-004: Production identity hardening](NFR-PORT-004.md) - Production uses federated credentials and Terraform-managed Entra apps, with no development shortcuts.

## Privacy

- [NFR-PRIV-001: No sensitive values in logs or traces](NFR-PRIV-001.md) - Tokens, argument values, prompts, responses and document content never reach logs or traces.
- [NFR-PRIV-002: Hidden resources are not disclosed](NFR-PRIV-002.md) - A caller cannot tell a resource they may not see from one that does not exist.
- [NFR-PRIV-003: Tenant data stays out of the repository](NFR-PRIV-003.md) - Tenant, app, group and user identifiers are never committed.
- [NFR-PRIV-004: Bounded data retention](NFR-PRIV-004.md) - Conversations and artifacts are kept for a limited, configured time.

## Quality

- [NFR-QUAL-001: Retrieval quality gate](NFR-QUAL-001.md) - Changes to retrieval are kept only if the retrieval evaluation does not get worse.

## Reliability

- [NFR-REL-001: Safe configuration reload](NFR-REL-001.md) - A bad configuration never replaces a good one, and each request sees one consistent version.
- [NFR-REL-002: Stable MCP sessions](NFR-REL-002.md) - There is one MCP client session per user and conversation, and the server holds no session state.
- [NFR-REL-003: Scale-out readiness](NFR-REL-003.md) - Per-instance state must move to shared stores before services run more than one instance.
- [NFR-REL-004: Repeatable data changes](NFR-REL-004.md) - Ingest and schema changes can be re-run safely.
- [NFR-REL-005: Durable event processing](NFR-REL-005.md) - Event workflows survive retries, duplicates, bursts and failures without double outcomes or loops.

## Security

- [NFR-SEC-001: Single enforcement point](NFR-SEC-001.md) - Authorization is decided only in the MCP server, never in prompts or agent code.
- [NFR-SEC-002: Deny by default](NFR-SEC-002.md) - Nothing is allowed unless a rule grants it, and a deny wins over any allow.
- [NFR-SEC-003: Strict token validation](NFR-SEC-003.md) - Only Entra v2 user tokens for this tenant and API are accepted.
- [NFR-SEC-004: Fail closed](NFR-SEC-004.md) - Missing or unverifiable identity or configuration means less access, never more.
- [NFR-SEC-005: Row-level security on all data](NFR-SEC-005.md) - Postgres row-level security is the last line of defence for data access and no role can bypass it.
- [NFR-SEC-006: Calls are made as the user](NFR-SEC-006.md) - Agents forward the user's own token; a service token is never used for user calls.
- [NFR-SEC-007: Secrets handling](NFR-SEC-007.md) - Secrets live only in the local env file or Secret Manager and are referenced, never embedded.
- [NFR-SEC-008: Controlled egress](NFR-SEC-008.md) - Outbound HTTP goes only to allowlisted hosts.
- [NFR-SEC-009: External content is untrusted](NFR-SEC-009.md) - Content from providers, sources and model extraction is treated as data, never as instructions or trusted structure.
- [NFR-SEC-010: Least-privilege runtime](NFR-SEC-010.md) - Each service gets only the credentials and environment it needs.
- [NFR-SEC-011: Browser-facing hardening](NFR-SEC-011.md) - Browser-reachable endpoints are hardened against content sniffing, cross-site requests and developer tooling exposure.
- [NFR-SEC-012: Sandboxed code execution](NFR-SEC-012.md) - Code written by agents runs only in ephemeral sandboxes with no production access.
- [NFR-SEC-013: Agents hold no write credentials](NFR-SEC-013.md) - Agents emit structured outcomes; a separate delivery service holds the credentials that write to external systems.

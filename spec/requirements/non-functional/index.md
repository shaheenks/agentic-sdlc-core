# Hosting

* [NFR-HOST-001: Hosted on Google Cloud](NFR-HOST-001.md) - Every platform component runs on Google Cloud.
* [NFR-HOST-002: Infrastructure as code](NFR-HOST-002.md) - All Google Cloud resources are defined in Terraform.
* [NFR-HOST-003: Separate environments](NFR-HOST-003.md) - Each environment has its own Google Cloud project, configuration and data.
* [NFR-HOST-004: Managed services first](NFR-HOST-004.md) - Components run on managed or serverless Google Cloud services.
* [NFR-HOST-005: Single region europe-west3](NFR-HOST-005.md) - The platform runs and keeps its data in europe-west3 (Frankfurt), with listed exceptions only.

# Architecture

* [NFR-ARCH-001: sdlc_ui is one container](NFR-ARCH-001.md) - The custom UI and its BFF are built, versioned and deployed as one container named sdlc_ui.
* [NFR-ARCH-002: Hostnames and service URLs are configuration](NFR-ARCH-002.md) - No hostname or URL is hard-coded; dependent service URLs come from environment variables.
* [NFR-ARCH-003: Self-contained components](NFR-ARCH-003.md) - Each deployable component lives in its own root folder and builds and tests on its own, with dependency URLs from environment variables.
* [NFR-ARCH-004: Knowledge backend isolated](NFR-ARCH-004.md) - Knowledge ingestion and search run as their own services; the MCP server only proxies to them.
* [NFR-ARCH-005: Google ADK agents and graph workflows](NFR-ARCH-005.md) - Agents are built with Google ADK and workflows are ADK graph workflows, deployed to Agent Runtime.
* [NFR-ARCH-006: Two MCP servers, one per class of caller](NFR-ARCH-006.md) - The platform always has exactly two MCP servers, user_agent_mcp and event_agent_mcp, classified by nature of usage, access pattern, capabilities and configuration; each agent deployment connects only to its own.

# Security

* [NFR-SEC-001: Authorization only in the platform's services](NFR-SEC-001.md) - Authorization is decided by the Access Policy and enforced by the services that own the resources, never in prompts, agents or the UI.
* [NFR-SEC-002: Deny by default, fail closed](NFR-SEC-002.md) - Anything not granted is denied, and unverifiable identity or configuration denies.
* [NFR-SEC-003: Tokens stay server side](NFR-SEC-003.md) - User tokens never reach the browser and are never logged or stored beyond need.
* [NFR-SEC-004: Where secrets live](NFR-SEC-004.md) - Users' connection secrets live, encrypted by the application, under a secrets/ prefix of the artifact bucket; every other secret lives in GCP Secret Manager and reaches services as environment variables.
* [NFR-SEC-005: Outbound host allowlist](NFR-SEC-005.md) - Components call only the external hosts declared for them.
* [NFR-SEC-006: Least-privilege service identities](NFR-SEC-006.md) - Each component runs as its own service account with only the roles it needs.
* [NFR-SEC-007: sdlc_ui behind Identity-Aware Proxy](NFR-SEC-007.md) - Only signed-in users of the organisation in the declared access groups reach sdlc_ui at all.

# Privacy

* [NFR-PRIV-001: No sensitive content in telemetry](NFR-PRIV-001.md) - Logs, traces and metrics carry no prompts, responses, tokens or argument values.
* [NFR-PRIV-002: Run transcripts under run access](NFR-PRIV-002.md) - Agent transcripts are kept only as part of the run, under the run's access rules and retention.

# Auditability

* [NFR-AUD-001: Audit every decision](NFR-AUD-001.md) - Every authentication, authorization decision, run start, human decision and activation is audited.
* [NFR-AUD-002: Audit retention](NFR-AUD-002.md) - Audit records go to the standard Cloud Logging bucket as structured JSON with a unique tag, kept 30 days.

# Observability

* [NFR-OBS-001: End-to-end trace per run](NFR-OBS-001.md) - One trace follows a run through every step, model call and tool call.
* [NFR-OBS-002: Operational metrics](NFR-OBS-002.md) - Operators see run, step, cost and wait-time metrics.
* [NFR-OBS-003: Event metadata on every trace of an unattended run](NFR-OBS-003.md) - Scheduled and event-triggered runs are traced and audited with the triggering event's metadata, end to end.

# Reliability

* [NFR-REL-001: 99.5% availability](NFR-REL-001.md) - sdlc_ui, the A2A router, user_agent_mcp, the Gemini Enterprise agent and the workflow engine are available 99.5% of each month in production.
* [NFR-REL-002: Multi-zone production](NFR-REL-002.md) - Production survives the loss of one zone in europe-west3.

# Performance

* [NFR-PERF-001: Application response under 5 seconds on average](NFR-PERF-001.md) - Requests to the platform's application components are answered in under 5 seconds on average; agent responses are excluded.

# Operability

* [NFR-OPS-001: Reproducible images](NFR-OPS-001.md) - Each deployable image is identified by its build inputs and promoted unchanged.
* [NFR-OPS-002: Local Docker Compose environment](NFR-OPS-002.md) - All self-hosted components run locally with Docker Compose, each pointing at local or GCP services through environment-variable profiles.
* [NFR-OPS-003: Revoke and replace a leaked system connection PAT](NFR-OPS-003.md) - A manual, documented procedure revokes a system connection PAT that has leaked, or may have, and puts a new one in service on event_agent_mcp.

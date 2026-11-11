# Functional

## SDLC actions

- [FR-ACT-001: SDLC action tools](FR-ACT-001.md) - Tools that review code, generate tests and approve designs.

## Artifacts

- [FR-ART-001: Save and manage artifacts](FR-ART-001.md) - The assistant saves documents for a user; only the owner can list, read or delete them.
- [FR-ART-002: Artifact versions](FR-ART-002.md) - A document keeps a stable id across versions and newer edits are never overwritten.
- [FR-ART-003: Download and review artifacts in the chat](FR-ART-003.md) - Owners download artifacts and review them in the chat with line comments.
- [FR-ART-004: Share artifacts with a team](FR-ART-004.md) - Owners can share an artifact with their team.

## Authorization

- [FR-AUTHZ-001: Selective disclosure of tools](FR-AUTHZ-001.md) - tools/list returns only the tools the caller's effective policy allows.
- [FR-AUTHZ-002: Per-call authorization with argument limits](FR-AUTHZ-002.md) - Every tool call is re-authorized, including team limits on argument values.
- [FR-AUTHZ-003: Role hierarchy with classification ceilings](FR-AUTHZ-003.md) - Roles inherit from one another and each caps the data classification its holder can read.
- [FR-AUTHZ-004: Per-user rate limits](FR-AUTHZ-004.md) - Calls are rate-limited per user from a platform baseline and team limits.
- [FR-AUTHZ-005: Data access granted per source](FR-AUTHZ-005.md) - Knowledge is readable only where the source's own access rule grants it, under the role's classification ceiling.
- [FR-AUTHZ-006: Team roles are scoped to their team](FR-AUTHZ-006.md) - A team role grants access only to that team's resources, never to another team's.

## Autonomous agents

- [FR-AUTO-001: Autonomous agents and event intake](FR-AUTO-001.md) - CI and operations agents run on events under their own workload identity.

## Configuration

- [FR-CFG-001: Access declared in configuration](FR-CFG-001.md) - Roles, teams, tools, skills, sources and limits are declared in versioned YAML, never in code.
- [FR-CFG-002: Explain and diff effective permissions](FR-CFG-002.md) - Operators can see what a persona may do and how a config change alters it.
- [FR-CFG-003: Immutable config bundles with rollback](FR-CFG-003.md) - Configuration is published as immutable versioned bundles, activated by a pointer and rolled back the same way.
- [FR-CFG-004: Admin view of the running configuration](FR-CFG-004.md) - Admins can inspect which configuration version a server is running.

## Connections

- [FR-CONN-001: Users connect their own accounts](FR-CONN-001.md) - Users add personal access tokens for external systems through a dedicated page, never through chat.
- [FR-CONN-002: Tools act as the user](FR-CONN-002.md) - Tools that reach external systems use the caller's own connection, after the policy check.
- [FR-CONN-003: Atlassian and Data Center connections](FR-CONN-003.md) - Users connect Atlassian Cloud and Data Center accounts, and connected tools use them as the user.
- [FR-CONN-004: Service connections for autonomous workflows](FR-CONN-004.md) - Autonomous workflows reach Jira, Confluence and Bitbucket through service connections held server-side; initially broad-scoped tokens, later OAuth or system principals.

## Conversations

- [FR-CONV-001: Conversation history](FR-CONV-001.md) - Users can list, reopen and delete their own conversations.
- [FR-CONV-002: Per-user memory](FR-CONV-002.md) - The assistant keeps long-term memory per user, readable only in that user's sessions.

## Documents

- [FR-DOC-001: Reviewed document flow](FR-DOC-001.md) - Documents are produced by brainstorm, confirmed brief, draft, isolated reviewers and resolution, then saved with their review.

## Identity

- [FR-IDN-001: Sign-in with Entra ID](FR-IDN-001.md) - Every surface requires a valid Microsoft Entra ID sign-in; there is no other identity provider.
- [FR-IDN-002: Membership from groups, app roles and direct members](FR-IDN-002.md) - A user's teams and roles come from Entra groups, Entra app roles and the per-environment direct-member list, combined as a union.
- [FR-IDN-003: Users can see their own access](FR-IDN-003.md) - A user can ask what they are allowed to do and why; only admins can view another user's policy.
- [FR-IDN-004: Revocation of access](FR-IDN-004.md) - A blocked user loses access on the next request and their stored connections are removed by a reconcile job.
- [FR-IDN-005: Workflow identity](FR-IDN-005.md) - Autonomous workflows authenticate with their own Entra workload identity and are authorized like any principal.

## Knowledge

- [FR-KNOW-001: Ingest declared sources](FR-KNOW-001.md) - Sources declared in configuration are loaded, chunked, embedded and tagged with their source and classification.
- [FR-KNOW-002: Knowledge search with citations](FR-KNOW-002.md) - Users search their team's knowledge and get answers with citations to the exact place.
- [FR-KNOW-003: Knowledge graph queries](FR-KNOW-003.md) - Users can follow relations between entities extracted from their sources.
- [FR-KNOW-004: PDF ingestion](FR-KNOW-004.md) - PDFs are ingested with page-level citations; OCR is opt-in per source.
- [FR-KNOW-005: Scheduled ingest](FR-KNOW-005.md) - Ingest runs on a schedule in the cloud environment.
- [FR-KNOW-006: Atlassian and Bitbucket sources](FR-KNOW-006.md) - Confluence spaces, Jira projects and Bitbucket repositories, Cloud and Data Center, can be declared and ingested as sources.
- [FR-KNOW-007: OCR for scanned PDFs](FR-KNOW-007.md) - PDFs without a text layer are read with model OCR, only for sources that opt in.
- [FR-KNOW-008: Source code graph](FR-KNOW-008.md) - Repositories are parsed into a symbol graph that queries can walk under the same access rules.
- [FR-KNOW-009: Images and diagrams](FR-KNOW-009.md) - Images and diagrams in sources are described and read with a multimodal model, for sources that opt in.
- [FR-KNOW-010: Diverse document formats](FR-KNOW-010.md) - Office documents, API specifications and structured data are ingested with format-aware chunking.

## Skills

- [FR-SKILL-001: Skills served per user](FR-SKILL-001.md) - Users see and load only the skills their policy allows.
- [FR-SKILL-002: Skill naming and layout](FR-SKILL-002.md) - Skill names are stable, globally unique identifiers validated at load.

## Surfaces

- [FR-SURF-001: Chat application](FR-SURF-001.md) - A web chat is the main surface for talking to the assistant.
- [FR-SURF-002: Agent-to-agent endpoint](FR-SURF-002.md) - Other agent platforms reach the assistant over A2A with the user's token.
- [FR-SURF-003: Direct MCP clients](FR-SURF-003.md) - IDE clients can connect straight to the MCP server.
- [FR-SURF-004: Catalogs for coding harnesses](FR-SURF-004.md) - Coding harnesses get the caller's tools, skills and knowledge catalogs straight from the MCP server.

## Teams

- [FR-TEAM-001: Team customization of behaviour](FR-TEAM-001.md) - Teams add instructions, skills and document-flow defaults that change behaviour but never permissions.
- [FR-TEAM-002: Team resolution and lock](FR-TEAM-002.md) - The assistant works broadly until a brief is confirmed, then locks to one of the user's own teams.

## Workflows

- [FR-WFL-001: Workflows are declared and classified](FR-WFL-001.md) - Each workflow is declared in configuration with its class, trigger, identity, access and outcome delivery.
- [FR-WFL-002: Event intake](FR-WFL-002.md) - One gateway receives CI and operational events, verifies the caller, matches a Trigger and publishes a normalised event.
- [FR-WFL-003: Event enrichment](FR-WFL-003.md) - Events are enriched with the workflow's agent context and real-time context before an agent runs.
- [FR-WFL-004: Build and test workflows](FR-WFL-004.md) - CI events start pull request analysis, code quality, security audit and change management workflows that report back to source control.
- [FR-WFL-005: Deploy and maintain workflows](FR-WFL-005.md) - Operational events start read-only diagnosis whose findings become incident records, with optional proposed fixes.
- [FR-WFL-006: Implementation workflow](FR-WFL-006.md) - An approved design or spec starts a sandboxed coding agent that delivers a first version of the code as a draft PR.

## Write actions

- [FR-WRITE-001: Write tools with user confirmation](FR-WRITE-001.md) - Tools that create issues, comments or pull requests on the user's behalf, confirmed in the UI.

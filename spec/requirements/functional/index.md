# Surfaces

* [FR-SURF-001: Custom UI](FR-SURF-001.md) - Users run and follow workflows in the platform's own web UI, sdlc_ui.
* [FR-SURF-002: A2A router](FR-SURF-002.md) - Gemini Enterprise, and later third-party A2A surfaces, reach user_agent through one A2A router, as the calling user.
* [FR-SURF-003: Gemini Enterprise app](FR-SURF-003.md) - Users run workflows from the Gemini Enterprise app, and the platform acts as the user signed in to Gemini Enterprise.
* [FR-SURF-004: Same behaviour on every surface](FR-SURF-004.md) - A user gets the same workflows, permissions, runs and artifacts whichever surface they use.
* [FR-SURF-005: Third-party AI surfaces over A2A](FR-SURF-005.md) - Users reach the platform's workflows from other AI surfaces that speak A2A, such as Microsoft Copilot, through the A2A router and with their own identity.
* [FR-SURF-006: Direct MCP access from coding harnesses](FR-SURF-006.md) - Coding harnesses such as Google Antigravity, Gemini CLI and Claude Code connect directly to user_agent_mcp with the user's Google account token, using only the tool groups declared for them.

# Identity

* [FR-IDN-001: Sign-in with Cloud Identity, federated from Entra ID](FR-IDN-001.md) - Users are Google accounts in the organisation's Cloud Identity account, signing in through Microsoft Entra ID.
* [FR-IDN-002: Act as the user end to end](FR-IDN-002.md) - Every tool call, data read and downstream call of a user's run is made as that user.
* [FR-IDN-003: Block list](FR-IDN-003.md) - A blocked user is refused on every surface.
* [FR-IDN-004: System identity for unattended runs](FR-IDN-004.md) - Scheduled and event-triggered runs act as the platform's system identity and carry the triggering event's metadata.

# Teams

* [FR-TEAM-001: Teams declared in configuration](FR-TEAM-001.md) - A user's teams, team roles and user groups are declared per environment in configuration.
* [FR-TEAM-002: Team context](FR-TEAM-002.md) - A user who belongs to several teams chooses which team a run is for.
* [FR-TEAM-003: Team runs visible to the team](FR-TEAM-003.md) - Members of a team see the team's runs and artifacts as their team role allows.
* [FR-TEAM-004: Many teams per user](FR-TEAM-004.md) - A user can belong to any number of teams and user groups, and sees what any of them grants.

# Authorization

* [FR-AUTHZ-001: Access declared in configuration](FR-AUTHZ-001.md) - All access rules come from declarative configuration, never from code or prompts.
* [FR-AUTHZ-002: Selective disclosure](FR-AUTHZ-002.md) - Users and their agents are shown only what the user may use.
* [FR-AUTHZ-003: Authorize every call](FR-AUTHZ-003.md) - Every workflow start, tool call and resource access is authorized, with its arguments, when it is made.
* [FR-AUTHZ-004: Data scope](FR-AUTHZ-004.md) - Knowledge reads are limited to the sources a user may read, up to their classification ceiling.
* [FR-AUTHZ-005: Rate limits and quotas](FR-AUTHZ-005.md) - Runs started and tool calls are limited per user and per team.
* [FR-AUTHZ-006: Tool groups per surface](FR-AUTHZ-006.md) - Each surface sees only the tool groups declared for it, on top of the user's own permissions.
* [FR-AUTHZ-007: Grants to teams and user groups](FR-AUTHZ-007.md) - Workflows, skills and tools are made available per team or per user group in configuration.
* [FR-AUTHZ-008: Per-user isolation of sessions, artifacts and secrets](FR-AUTHZ-008.md) - A user's sessions, artifacts and connection secrets belong to that user alone and are not visible to anyone else.

# Configuration

* [FR-CFG-001: Versioned configuration bundles](FR-CFG-001.md) - Configuration is loaded only from validated, versioned bundles.
* [FR-CFG-002: Permission diff](FR-CFG-002.md) - Reviewers see who gains or loses what between two configuration versions.
* [FR-CFG-003: Activation per environment](FR-CFG-003.md) - A bundle becomes active in an environment through an explicit, audited action.
* [FR-CFG-004: YAML configuration in config/](FR-CFG-004.md) - Teams, user groups, grants, workflows, skills, tools, surfaces and sources are declared in schema-validated YAML in the config folder.
* [FR-CFG-005: Configuration bucket](FR-CFG-005.md) - The active configuration is published to a dedicated Cloud Storage bucket that the MCP server reads while answering requests.

# Workflows

* [FR-WFL-001: Workflow catalog](FR-WFL-001.md) - Users run pre-defined workflows that authors define, review and publish.
* [FR-WFL-002: Workflow definition](FR-WFL-002.md) - A workflow is a graph of typed steps: agent, tool, human task and sub-workflow.
* [FR-WFL-003: Start a run](FR-WFL-003.md) - A permitted user starts a run of a workflow for themselves or a team from any surface.
* [FR-WFL-004: Durable runs](FR-WFL-004.md) - A run survives restarts and can be resumed, retried or cancelled.
* [FR-WFL-005: Run limits](FR-WFL-005.md) - Each run stops when it exceeds its declared time, cost or step limits.
* [FR-WFL-006: Reproducible runs](FR-WFL-006.md) - A run uses exactly the workflow and skill versions pinned when it started.
* [FR-WFL-007: Team parameter overrides](FR-WFL-007.md) - A team overrides only the parameters a global workflow declares as overridable; teams cannot fork workflows.
* [FR-WFL-008: Run events and history](FR-WFL-008.md) - Surfaces follow a run live and list past runs.
* [FR-WFL-009: Resume after signing in again](FR-WFL-009.md) - A user who signs out, or whose sign-in expires, signs in again and continues their own sessions and waiting runs.

# Triggers

* [FR-TRIG-001: Event triggers](FR-TRIG-001.md) - Runs start from events in downstream systems, such as a pull request opened.
* [FR-TRIG-002: Schedules](FR-TRIG-002.md) - Runs start on schedules declared in configuration.
* [FR-TRIG-003: Results of unattended runs go back to the systems involved](FR-TRIG-003.md) - A scheduled or event-triggered run delivers its results to the downstream systems it serves, such as a comment on the pull request that started it.
* [FR-TRIG-004: CI workflow events](FR-TRIG-004.md) - ci_workflow_agent handles events from CI workflows, such as a pipeline run that failed, and reports back to the systems involved.
* [FR-TRIG-005: Deployment and platform events](FR-TRIG-005.md) - operations_agent handles events from deployment and platform services, such as a failed rollout or a platform alert, and reports back to the systems involved.

# Human tasks

* [FR-HUM-001: Human tasks pause a run](FR-HUM-001.md) - A run waits for a person to approve, review, choose or supply input.
* [FR-HUM-002: Task routing](FR-HUM-002.md) - Every human task is assigned to the user whose run raised it; routing to other users, teams or team roles is not needed for now.
* [FR-HUM-003: Task signals inside the platform](FR-HUM-003.md) - Open human tasks are signalled to their user inside the platform only; there are no reminders, expiry or outside notifications.
* [FR-HUM-004: Separation of duties](FR-HUM-004.md) - Where a step requires it, the run's starter cannot approve their own run.
* [FR-HUM-005: Approval before writes](FR-HUM-005.md) - Write actions on downstream systems run only after an approval where the workflow requires one.

# Agent steps

* [FR-AGT-001: Bounded agent steps](FR-AGT-001.md) - An agent step uses only its bound skills and permitted tools, and returns output in its declared schema.
* [FR-AGT-002: Sub-agents](FR-AGT-002.md) - An agent step can use isolated sub-agents declared by the workflow.
* [FR-AGT-003: User agent MCP server](FR-AGT-003.md) - Agents on Agent Runtime act for the user through user_agent_mcp, which scopes every action to the user in the verified token.
* [FR-AGT-004: Event agent MCP server](FR-AGT-004.md) - Agents in scheduled and event-triggered runs act as the system identity through event_agent_mcp, a standalone MCP server separate from user_agent_mcp.
* [FR-AGT-005: Ad-hoc knowledge search and brainstorm chat](FR-AGT-005.md) - Users chat with user_agent outside any workflow, to search knowledge and brainstorm, acting as themselves.

# Skills

* [FR-SKILL-001: Skill packages](FR-SKILL-001.md) - Agent know-how ships as versioned skill packages, global or team-specific.

# Connections

* [FR-CONN-001: Per-user connections](FR-CONN-001.md) - Users link their own accounts on downstream systems.
* [FR-CONN-002: Reconnect instead of fail](FR-CONN-002.md) - A run that needs a missing or expired connection asks the user to connect.
* [FR-CONN-003: Downstream systems](FR-CONN-003.md) - The platform reads and writes source control, issue tracking and documentation systems.
* [FR-CONN-004: System connections](FR-CONN-004.md) - Unattended runs reach downstream systems through platform-owned connections scoped by configuration.
* [FR-CONN-005: Secrets never pass through agents](FR-CONN-005.md) - Personal access tokens are entered outside the conversation and never reach a model, an agent or a tool result.

# Knowledge

* [FR-KNOW-001: Ingest declared sources](FR-KNOW-001.md) - Knowledge sources declared in configuration are ingested and kept fresh.
* [FR-KNOW-002: Knowledge search](FR-KNOW-002.md) - Agents search knowledge by meaning, keyword and graph through the MCP server, which proxies to the knowledge search service.
* [FR-KNOW-003: Ingest status](FR-KNOW-003.md) - Operators see each source's ingest status.
* [FR-KNOW-004: Knowledge scope: broad in chat, team in workflows](FR-KNOW-004.md) - Ad-hoc knowledge search and brainstorming use everything the user may read; a predefined workflow sets the team scope when it starts, and changing it needs the user's explicit confirmation in chat.

# Artifacts

* [FR-ART-001: Artifacts with lineage](FR-ART-001.md) - Runs store their outputs as artifacts linked to the run and step.
* [FR-ART-002: Artifact ownership](FR-ART-002.md) - An artifact belongs to the user whose run produced it and is readable only by that user.
* [FR-ART-003: Artifact retention of 7 days](FR-ART-003.md) - Artifacts live in a dedicated bucket and are deleted 7 days after they are created.

# Models

* [FR-MDL-001: Model classes](FR-MDL-001.md) - Workflows name a model class; configuration maps it to a concrete model.
* [FR-MDL-002: Usage limits](FR-MDL-002.md) - Usage is held in check by approximate rate limits on tool calls at the MCP servers; token and cost budgets come later.

# SDLC flow

* [FR-SDLC-001: Approved artifact chain](FR-SDLC-001.md) - Each stage of the SDLC flow ends with an approved artifact in its system of record (Jira for features and stories, the repository from the design on), and the next stage starts from it.
* [FR-SDLC-002: Features and user stories in Jira](FR-SDLC-002.md) - user_agent drafts features and user stories with the user, from an idea, ticket or bug record, and adds them to Jira as the user once the user approves them in chat.
* [FR-SDLC-003: Design specification from approved Jira items](FR-SDLC-003.md) - user_agent drafts a design specification from an approved Jira feature and its user stories, read with the user's own connection; it is reviewed by fresh-context reviewers and approved by the user in chat.
* [FR-SDLC-004: Fresh-context document review](FR-SDLC-004.md) - Documents are reviewed by reviewer agents that read only the written document and permitted evidence, never the drafting conversation; the user decides which findings to apply.
* [FR-SDLC-005: Design specification pull request](FR-SDLC-005.md) - Once the user approves a design specification, user_agent opens a pull request with it on the respective repository, as the user; merging it hands the work to ci_workflow_agent.
* [FR-SDLC-006: Implementation by ci_workflow_agent](FR-SDLC-006.md) - ci_workflow_agent turns a merged design specification into an implementation plan and, once the plan is merged, into a pull request with code and tests.
* [FR-SDLC-007: Security vulnerability analysis of pull requests](FR-SDLC-007.md) - A ci_workflow_agent workflow of its own analyses each pull request in a declared repository for security vulnerabilities and posts the findings; people approve and merge.
* [FR-SDLC-008: Deployment handling](FR-SDLC-008.md) - operations_agent follows builds and deployments, reports their outcome where the change came from, checks health after a rollout, and explains failures.
* [FR-SDLC-009: Alert triage and log analysis](FR-SDLC-009.md) - operations_agent diagnoses alerts read-only from logs, metrics, traces and recent changes, and posts the diagnosis with evidence.
* [FR-SDLC-010: Incident and bug reporting](FR-SDLC-010.md) - operations_agent records incidents and bugs from diagnosed alerts and failed deployments, so they can re-enter the flow as new features and stories.
* [FR-SDLC-011: Quality assurance analysis of pull requests](FR-SDLC-011.md) - A ci_workflow_agent workflow of its own analyses each pull request in a declared repository for quality and posts the findings; people approve and merge.
* [FR-SDLC-012: Jira tasks from findings](FR-SDLC-012.md) - Findings that need someone's attention are raised as Jira tasks, linked to the user stories, feature or incident they concern; Jira is the notification channel.

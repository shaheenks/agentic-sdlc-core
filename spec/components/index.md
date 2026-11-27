# Experience

* [A2A Router](a2a-router.md) - One A2A router in front of user_agent, used by Gemini Enterprise now and by third-party A2A surfaces such as Microsoft Copilot once enabled, acting as the calling user.
* [Gemini Enterprise Agent](gemini-enterprise-agent.md) - The platform's agent deployment on Gemini Enterprise Platform, registered in the Gemini Enterprise app so users run workflows from Gemini Enterprise directly.
* [sdlc_ui](sdlc-ui.md) - The custom web UI and its backend-for-frontend, built and deployed as one container, where users and teams start workflows, follow runs, answer human tasks and open artifacts.

# Control

* [Access Policy](access-policy.md) - Resolves a user's effective permissions from declared roles and decides, deny by default, every request to list or use a workflow, tool, skill or data source.
* [Configuration Registry](configuration-registry.md) - Schema-validated YAML in config/ - teams, user groups, grants, workflows, skills, tools, surfaces, sources - compiled into versioned bundles on a dedicated configuration bucket that services read while answering requests.
* [Directory](directory.md) - Knows the platform's users and teams, who belongs to which team, and in what team role.
* [Identity](identity.md) - Establishes who the user of each request is, under the environment's identity mode, and refuses anyone it cannot verify.
* [Workflow Catalog](workflow-catalog.md) - The library of pre-defined, versioned SDLC workflow definitions - their steps, inputs, outputs, gates and who may run them.

# Execution

* [Agent Runtime](agent-runtime.md) - Executes the agent nodes of a workflow with Google ADK on Agent Runtime - loads the node's skills, reasons with Gemini and calls tools through user_agent_mcp, as the user.
* [ci_workflow_agent](ci-workflow-agent.md) - The event-based agent for code: turns a merged design specification into a plan and then a pull request, and runs two review workflows on pull requests: security vulnerability analysis and quality assurance analysis.
* [Code Workspace](code-workspace.md) - Cloud Run jobs that build and test a change: the system job checks out, applies ci_workflow_agent's changes, runs the repository's commands and pushes the working branch; the credential-free user job only builds an archive user_agent_mcp fetched as the user.
* [Event Gateway](event-gateway.md) - Starts workflow runs from schedules and from events in downstream systems, such as a pull request opened or a ticket moved.
* [Human Tasks](human-tasks.md) - Pauses a run for its own user - an approval, a review, a missing input - and resumes the run with the answer, using ADK human input nodes.
* [operations_agent](operations-agent.md) - The event-based agent for operations: follows deployments, triages alerts with log analysis, and reports incidents and bugs back into the flow.
* [user_agent](user-agent.md) - The interactive agent: knowledge search and brainstorming, features and user stories added to Jira, design specifications from approved Jira items with fresh-context review, and the design pull request, acting as the user.
* [Workflow Engine](workflow-engine.md) - Runs catalog workflows durably for a user, a team or the system identity, as ADK 2.0 graph workflows on Agent Runtime with state in Agent Runtime Sessions.

# Capability

* [Connectors](connectors.md) - Adapters to downstream SDLC systems - source control, issue trackers, wikis, CI - that read and write as the user with the user's own connection.
* [Control Repository](control-repository.md) - The shared rules of a team's sdlc-control repository - feature branches, where each artifact lives, who approved it, and the record of every write made from it - used by both MCP servers.
* [event_agent_mcp](event-agent-mcp.md) - The standalone MCP server for scheduled and event-triggered runs: agents call it as the system identity, and it reaches only system connections and system artifacts.
* [Skill Library](skill-library.md) - Versioned instruction packages that teach an agent step how to do one SDLC task, global or team-specific.
* [user_agent_mcp](user-agent-mcp.md) - The MCP server for agents acting for a user: sdlc_ui and agents on Agent Runtime call it for a verified user, and every action is scoped to that user's ID.
* [Workspace Runner](workspace-runner.md) - The shared code both MCP servers use to start the Code Workspace - request folders in the artifact bucket, the Cloud Run job execution and its result - for the system job and the credential-free user job.

# Knowledge

* [Ingest Pipeline](ingest-pipeline.md) - Reads declared knowledge sources, chunks, embeds and extracts a knowledge graph, tagging every record with its source and classification.
* [Knowledge Search](knowledge-search.md) - A separately hosted search service over the knowledge graph backend: semantic, keyword, hybrid and graph queries, filtered by the data-scope attribute the MCP server sends.
* [Knowledge Store](knowledge-store.md) - Stores chunks, embeddings and the knowledge graph and answers semantic, keyword and graph queries, filtered to what the caller may read.

# Records

* [Artifact Store](artifact-store.md) - A dedicated Cloud Storage bucket, mounted by the MCP servers, for the files runs produce (deleted 7 days after creation) and, for now, connection secrets; everything in it belongs to one user or to the system identity.
* [Audit Log](audit-log.md) - Append-only record of every authentication, authorization decision, run, human decision and configuration activation, without secrets or argument values.

# Platform

* [GCP Foundation](gcp-foundation.md) - The Google Cloud base every component runs on - projects per environment, networking, IAM and service accounts, regions and the Terraform that defines them.
* [Observability](observability.md) - Traces, metrics and logs across a run - from trigger through agent steps and tool calls to data stores - without sensitive content.
* [Secrets](secrets.md) - Keeps users' connection secrets encrypted under the artifact bucket's secrets/users/ prefix, and every other secret in GCP Secret Manager delivered as environment variables; never returned to agents or logs.

---
type: System
title: Agentic SDLC platform
description: What the platform is, its workflows, who uses it, what it connects to and what is in scope.
tags: [system, context]
status: draft
sources:
  - id: design
    resource: ../../docs/designs/workflow-platform.md
    title: Workflow platform target design
  - id: arch
    resource: ../../docs/ARCHITECTURE.md
    title: System architecture (as built)
  - id: inventory
    resource: ../../docs/FEATURE_INVENTORY.md
    title: Feature inventory (baseline 2026-11-08)
  - id: v03
    resource: ../../docs/plans/version-03.md
    title: Implementation plan version-03
  - id: playbook
    resource: https://claude.com/resources/articles/the-ai-native-sdlc-playbook
    title: The AI-Native SDLC Playbook
  - id: egm
    resource: https://egm.dev/
    title: Elephant-Goldfish Model
---

# Purpose

Engineers use AI agents for software-delivery work: planning and design, building and testing,
deploying and maintaining. The platform is built from **workflows**. Each one is an agent, or a
chain of agents, whose context (skills, tools and knowledge) comes from a central MCP server,
filtered by the identity it runs as.

Users have a platform role (`viewer` for the common knowledge, skills and tools, or `admin` for
everything) and, per team, a team role (`member`, or the optional `approver` for approval and
elevated access). A team role applies only within its own team.

One MCP server and API backend serves everything today. A workflow gets a dedicated MCP backend
whenever least privilege or identity separation requires it. User-led workflows reach dependent
systems with the user's own connection. Autonomous workflows use service connections held only
by server-side components: broad-scoped tokens in the initial phases, OAuth or system principals
later.

Each principal sees only the tools, skills and knowledge its identity allows (*selective
disclosure*). Declarative configuration decides the rules; the MCP server enforces them, backed by
database row-level security.

The design follows two models:
- The AI-Native SDLC Playbook: every stage commits an artifact that the next stage reads, humans
  approve at gates, and autonomy is tiered.
- The Elephant-Goldfish Model: a deep-context agent drafts, and isolated reviewers critique.

The target design is [docs/designs/workflow-platform.md](../../docs/designs/workflow-platform.md).

# Workflows

| Class | Started by | Runs as | Outcome |
|---|---|---|---|
| Plan and design (user-led; built as `user_agent`) | A user in a chat surface | The user | Documents, reviews and answers to the user |
| Build and test (autonomous) | CI events: PRs, pipelines | The workflow's own identity | Findings in source control |
| Deploy and maintain (autonomous) | Operational events: alerts, logs | The workflow's own identity | Incident records, proposed fixes |
| Implementation (autonomous, gated) | An approved spec or design | The workflow's own identity, in a sandbox | A draft PR for human review |

A workflow is classified by its source events, the identity it runs as, the systems it may reach,
and where it delivers its outcome. All four are declared in configuration, so new workflows and
actions are added without changing the platform.

# Actors

| Actor | Wants |
|---|---|
| Engineer (platform `viewer`; team `member`) | Answers from common and team knowledge, documents and reviews, and findings on their own changes |
| Team approver (optional team role) | To approve specs and designs for the team, to use the team's elevated skills and tools, and to review agent-written code |
| Team owner | To shape the assistant for the team: instructions, skills, document templates, sources, workflows |
| Platform admin | To declare access, publish configuration, onboard teams, block users |
| Operator | To deploy, observe, audit and roll back |
| External agent platform or coding harness | To reach the assistant, or the MCP server's catalogs, for a signed-in user |
| Workflow principal | To act on CI, operational and approval events under its own identity |

# External systems

| System | Role |
|---|---|
| Microsoft Entra ID | The only identity provider: sign-in, app roles (all membership; groups are not used), workload identities |
| Gemini on Vertex AI | The model for agents, embeddings, graph extraction, OCR and image understanding |
| Gemini Enterprise | A2A surface for users, with the user's Entra token. On GCP, also sessions and the optional Agent Registry |
| Microsoft Copilot and other third-party agent platforms | A2A surfaces for users, with the user's Entra token |
| Coding harnesses (Antigravity, IDEs) | Direct MCP clients for the tools, skills and knowledge catalogs |
| GitHub, Bitbucket (Cloud and Data Center), Jira, Confluence | Knowledge sources; systems tools reach as the user or workflow; CI and approval event sources; Jira also receives ops findings as tickets |
| GitHub Actions, Bitbucket Pipelines | CI event sources |
| GCP Cloud Monitoring and Logging, on-premise Kubernetes, Splunk | Operational event sources that push to the event endpoint, and real-time context |
| Google Cloud | Hosting: Cloud Run services and jobs (including the ADK implementation agent), Cloud SQL (PostgreSQL + pgvector), Cloud Storage, Secret Manager, Pub/Sub, tracing; optional Agent Gateway |

# Scope

In scope:
- the four workflow classes and their surfaces;
- the MCP server and its catalogs;
- the access model and its configuration;
- event intake, enrichment and outcome delivery;
- knowledge ingestion and retrieval, including code, images and diverse formats;
- skills and team customization;
- artifacts, user connections and sessions;
- audit and tracing;
- deployment locally and on GCP.

Out of scope today:
- workflows at tier `act` (changing a system without human approval);
- user-confirmed write tools before version-03 P7;
- pulling from on-premise Kubernetes and Splunk (push only for now);
- long-term memory (only sessions for now);
- environments beyond development.

See the `planned` and `parked` requirements.

# Specification

- [Functional requirements](../requirements/functional/index.md) - what the system does.
- [Non-functional requirements](../requirements/non-functional/index.md) - qualities and
  constraints it must hold.
- [Components](../components/index.md) - the parts of the system and the requirements each
  satisfies; the [traceability matrix](../traceability.md) shows coverage and gaps.
- [Rule sets](../rules/index.md) - binding working rules per area.
- [Conventions](../conventions.md) - how this bundle is organised and how changes are proposed.

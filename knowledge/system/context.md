---
type: System
title: Agentic SDLC platform
description: What the platform is, who uses it, what it connects to and what is in scope.
tags: [system, context]
status: draft
sources:
  - id: arch
    resource: ../../docs/ARCHITECTURE.md
    title: System architecture
  - id: inventory
    resource: ../../docs/FEATURE_INVENTORY.md
    title: Feature inventory (baseline 2026-11-08)
  - id: v03
    resource: ../../docs/plans/version-03.md
    title: Implementation plan version-03
---

# Purpose

Engineers use an AI assistant for software-delivery work: writing user stories, reviewing designs,
generating tests, reviewing code and answering questions about their team's systems. The assistant
is an agent built from skills. The skills, tools and team knowledge it can use come from a central
MCP server.

Each user sees only the tools, skills and knowledge their identity allows (*selective
disclosure*). Declarative configuration decides the rules; the MCP server enforces them, backed by
database row-level security.

# Actors

| Actor | Wants |
|---|---|
| Engineer (viewer, developer, lead) | Answers from team knowledge, documents, reviews, actions on their own repositories |
| Team owner | To shape the assistant for the team: instructions, skills, document templates, sources |
| Platform admin | To declare access, publish configuration, onboard teams, block users |
| Operator | To deploy, observe, audit and roll back |
| External agent platform or IDE | To reach the assistant or the MCP server for a signed-in user |
| Autonomous agent (planned) | To act on CI and operations events under its own identity |

# External systems

| System | Role |
|---|---|
| Microsoft Entra ID | The only identity provider: sign-in, groups, app roles |
| Gemini on Vertex AI | The model for agents, embeddings, graph extraction and OCR |
| GitHub, Bitbucket, Jira, Confluence | Knowledge sources, and systems the tools reach as the user |
| Google Cloud | Hosting for the cloud environment: compute, database, storage, secrets, tracing |

# Scope

In scope: the assistant and its surfaces, the MCP server, the access model and its configuration,
knowledge ingestion and retrieval, skills and team customization, artifacts, user connections,
audit and tracing, and deployment locally and on GCP.

Out of scope today: write actions on external systems, autonomous agents, and environments beyond
development (see the `planned` and `parked` requirements).

# Specification

- [Functional requirements](../requirements/functional/index.md) - what the system does.
- [Non-functional requirements](../requirements/non-functional/index.md) - qualities and
  constraints it must hold.
- [Conventions](../conventions.md) - how this bundle is organised.

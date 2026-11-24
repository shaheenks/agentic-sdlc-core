---
type: Component
title: "user_agent"
description: "The interactive agent: knowledge search and brainstorming, features and user stories added to Jira, design specifications from approved Jira items with fresh-context review, and the design pull request, acting as the user."
tags: [component, execution, agent]
status: draft
x-layer: execution
x-folder: interactive_agents/user_agent/
x-depends-on: [/components/agent-runtime, /components/workflow-engine, /components/human-tasks, /components/skill-library, /components/user-agent-mcp]
x-satisfies: [/requirements/functional/FR-AGT-005, /requirements/functional/FR-SDLC-001, /requirements/functional/FR-SDLC-002, /requirements/functional/FR-SDLC-003, /requirements/functional/FR-SDLC-004, /requirements/functional/FR-SDLC-005, /requirements/non-functional/NFR-ARCH-005, /requirements/non-functional/NFR-ARCH-006, /requirements/non-functional/NFR-HOST-001, /requirements/functional/FR-KNOW-004]
---

# Purpose

The agent users work with, from sdlc_ui and from Gemini Enterprise through the [A2A Router](a2a-router.md). It
carries an idea from conversation to an approved design and hands it to implementation. It is the *elephant* of the
Elephant-Goldfish Model: it holds the whole conversation, and its documents are reviewed by reviewers that do not.

# Responsibilities

- Knowledge search and brainstorming in ad-hoc chat with broad knowledge scope; a predefined workflow sets the
  team scope, and changing it needs the user's confirmation in chat
  ([FR-AGT-005](../requirements/functional/FR-AGT-005.md), [FR-KNOW-004](../requirements/functional/FR-KNOW-004.md)).
- Features and user stories from an idea, ticket or bug record; added to Jira as the user once the user approves
  them in chat ([FR-SDLC-002](../requirements/functional/FR-SDLC-002.md)).
- A design specification from an approved Jira feature and its stories, read as the user, approved by the user
  in chat ([FR-SDLC-003](../requirements/functional/FR-SDLC-003.md)).
- Fresh-context review of each document, applying only the fixes the user approves
  ([FR-SDLC-004](../requirements/functional/FR-SDLC-004.md)).
- After approval of the design, a pull request with it on the respective repository, with the user's own
  connection ([FR-SDLC-005](../requirements/functional/FR-SDLC-005.md)).

# Out of scope

- Implementing, reviewing pull requests, deploying and operating: the event-based agents,
  [ci_workflow_agent](ci-workflow-agent.md) and [operations_agent](operations-agent.md).
- Approving its own documents: the run's own user does that.

# Interfaces

- Provides: the ADK agent and the SDLC graph workflows of the interactive deployment; chat.
- Consumes: user_agent_mcp tools (knowledge search, artifacts, connections, Jira and repository reads and writes as the user), skills,
  human tasks, Gemini on Vertex AI.

# Depends on

- [Agent Runtime](agent-runtime.md)
- [Workflow Engine](workflow-engine.md)
- [Human Tasks](human-tasks.md)
- [Skill Library](skill-library.md)
- [user_agent_mcp](user-agent-mcp.md)

# Owns

- Nothing durable; drafts are the user's artifacts, and run state lives in the session.

# Requirements

- [FR-AGT-005: Ad-hoc knowledge search and brainstorm chat](../requirements/functional/FR-AGT-005.md)
- [FR-SDLC-001: Approved artifact chain](../requirements/functional/FR-SDLC-001.md)
- [FR-SDLC-002: Features and user stories in Jira](../requirements/functional/FR-SDLC-002.md)
- [FR-SDLC-003: Design specification from approved Jira items](../requirements/functional/FR-SDLC-003.md)
- [FR-SDLC-004: Fresh-context document review](../requirements/functional/FR-SDLC-004.md)
- [FR-SDLC-005: Design specification pull request](../requirements/functional/FR-SDLC-005.md)
- [NFR-ARCH-005: Google ADK agents and graph workflows](../requirements/non-functional/NFR-ARCH-005.md)
- [NFR-ARCH-006: Two MCP servers, one per class of caller](../requirements/non-functional/NFR-ARCH-006.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [FR-KNOW-004: Knowledge scope: broad in chat, team in workflows](../requirements/functional/FR-KNOW-004.md)

# Realisation

- Python, Google ADK, in `interactive_agents/user_agent/`, on the interactive Agent Runtime deployment.
- Reviewers run as ADK sub-agents with their own context, each given only the document and permitted evidence.
- Stage instructions and reviewer standards are skills in `skills/` (SKILL.md).

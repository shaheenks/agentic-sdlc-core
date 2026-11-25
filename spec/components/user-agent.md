---
type: Component
title: "user_agent"
description: "The interactive agent: knowledge search and brainstorming, features and user stories added to Jira, design specifications from approved Jira items with fresh-context review, and the design pull request, acting as the user."
tags: [component, execution, agent]
status: draft
x-layer: execution
x-folder: interactive_agents/user_agent/
x-depends-on: [/components/agent-runtime, /components/workflow-engine, /components/human-tasks, /components/skill-library, /components/user-agent-mcp]
x-satisfies: [/requirements/functional/FR-AGT-005, /requirements/functional/FR-SDLC-001, /requirements/functional/FR-SDLC-002, /requirements/functional/FR-SDLC-003, /requirements/functional/FR-SDLC-004, /requirements/functional/FR-SDLC-005, /requirements/non-functional/NFR-ARCH-005, /requirements/non-functional/NFR-ARCH-006, /requirements/non-functional/NFR-HOST-001, /requirements/functional/FR-KNOW-004, /requirements/functional/FR-SDLC-013]
---

# Purpose

The agent users work with, from sdlc_ui and from Gemini Enterprise through the [A2A Router](a2a-router.md). It
carries an idea from conversation to an approved design and hands it to implementation. It is the *elephant* of the
Elephant-Goldfish Model: it holds the whole conversation, and its documents are reviewed by reviewers that do not.

# Responsibilities

- Knowledge search and brainstorming in ad-hoc chat with broad knowledge scope; a predefined workflow sets the
  team scope, and changing it needs the user's confirmation in chat
  ([FR-AGT-005](../requirements/functional/FR-AGT-005.md), [FR-KNOW-004](../requirements/functional/FR-KNOW-004.md)).
- Features and user stories from an idea, ticket or bug record, kept as the user's own artifact; added to Jira as
  the user only when the user asks and a person has merged them on the team's control repository
  ([FR-SDLC-002](../requirements/functional/FR-SDLC-002.md), [DEC-0012](../decisions/DEC-0012.md)).
- A design specification from the user's own feature artifact or a published Jira feature
  ([FR-SDLC-003](../requirements/functional/FR-SDLC-003.md)).
- Fresh-context review of each document, applying only the fixes the user chooses
  ([FR-SDLC-004](../requirements/functional/FR-SDLC-004.md)).
- When the user hands a design on, a pull request with it on the team's control repository, with the user's own
  connection; its merge is the approval and the hand-off ([FR-SDLC-005](../requirements/functional/FR-SDLC-005.md),
  [FR-SDLC-013](../requirements/functional/FR-SDLC-013.md)).

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
- [FR-SDLC-002: Features and user stories](../requirements/functional/FR-SDLC-002.md)
- [FR-SDLC-003: Design specification](../requirements/functional/FR-SDLC-003.md)
- [FR-SDLC-004: Fresh-context document review](../requirements/functional/FR-SDLC-004.md)
- [FR-SDLC-005: Design specification hand-off](../requirements/functional/FR-SDLC-005.md)
- [NFR-ARCH-005: Google ADK agents and graph workflows](../requirements/non-functional/NFR-ARCH-005.md)
- [NFR-ARCH-006: Two MCP servers, one per class of caller](../requirements/non-functional/NFR-ARCH-006.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [FR-KNOW-004: Knowledge scope: broad in chat, team in workflows](../requirements/functional/FR-KNOW-004.md)
- [FR-SDLC-013: Team control repository](../requirements/functional/FR-SDLC-013.md)

# Realisation

- Python, Google ADK, in `interactive_agents/user_agent/`, on the interactive Agent Runtime deployment.
- Reviewers run as ADK sub-agents with their own context, each given only the document and permitted evidence.
- Stage instructions and reviewer standards are skills in `skills/` (SKILL.md).
- Built for ad-hoc chat (phase 3): an ADK agent whose tools are user_agent_mcp's, listed for the session's
  user; it answers from knowledge search with cited links and saves artifacts when the user agrees. A chat is
  titled from its first message.
- Built (phase 4a milestone 3): four ADK graph workflows, which the chat agent calls as tools, in an ADK `App`
  that is resumable, so a workflow waiting for the user continues with the answer
  ([DEC-0012](../decisions/DEC-0012.md)):
  - `features_and_stories` and `design_specification` draft with the stage skill and run the review loop; the
    draft is returned for the user to save as their own artifact, and nothing is written elsewhere. A design from
    the user's own feature checks nothing; from a Jira key or control ID it needs the feature approved on the
    team's control repository, recorded in Jira and In Design.
  - The review loop: the seven reviewers run in parallel as single-turn agents that receive only the document (and
    the stories it must satisfy), never the conversation, with read-only tools; their JSON findings are merged and
    numbered. A round without blockers or majors repeats until two in a row; otherwise the user chooses which
    findings to apply (`adk_request_input`), a reviser applies them, and the next round starts; from round five the
    question says so ([FR-SDLC-004](../requirements/functional/FR-SDLC-004.md)).
  - `publish_feature` and `hand_off_design`, only when the user asks: open the pull request on the team's control
    repository, wait for the user to say it is merged, check the approval through user_agent_mcp (back to waiting
    while it is not), then create the Jira issues or link the design to its Jira feature.
  - Every workflow first sets the run's team (`sdlc_team` in session state, sent as `X-SDLC-Team`): changing a
    chat's team needs the user's yes, and a team the user is not in is refused by user_agent_mcp and the previous
    scope restored ([FR-KNOW-004](../requirements/functional/FR-KNOW-004.md)).
  - Deterministic steps call user_agent_mcp directly as the session's user (`McpCaller`), so approvals are checked
    by the server. The skills ship inside the package (`user_agent/skills`, copied by `deploy.py`).
  - Tested in ADK with a scripted model and a faked user_agent_mcp; the answers come back through sdlc_ui in
    milestone 4.

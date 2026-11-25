---
type: Component
title: sdlc_ui
description: The custom web UI and its backend-for-frontend, built and deployed as one container, where users and teams start workflows, follow runs, answer human tasks and open artifacts.
tags: [component, experience]
status: draft
x-layer: experience
x-folder: sdlc_ui/
x-depends-on: [/components/identity, /components/workflow-engine, /components/human-tasks, /components/artifact-store, /components/connectors, /components/workflow-catalog, /components/user-agent-mcp]
x-satisfies: [/requirements/functional/FR-SURF-001, /requirements/functional/FR-SURF-004, /requirements/functional/FR-IDN-001, /requirements/functional/FR-TEAM-002, /requirements/functional/FR-TEAM-003, /requirements/functional/FR-TEAM-004, /requirements/functional/FR-WFL-003, /requirements/functional/FR-WFL-008, /requirements/functional/FR-CONN-001, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-ARCH-001, /requirements/non-functional/NFR-ARCH-002, /requirements/non-functional/NFR-ARCH-003, /requirements/non-functional/NFR-SEC-001, /requirements/non-functional/NFR-SEC-003, /requirements/non-functional/NFR-SEC-007, /requirements/non-functional/NFR-REL-001, /requirements/non-functional/NFR-PERF-001, /requirements/non-functional/NFR-OPS-001, /requirements/non-functional/NFR-OPS-002, /requirements/functional/FR-WFL-009, /requirements/functional/FR-AGT-005]
---

# Purpose

The platform's own surface. One stack: the browser UI and the backend-for-frontend (BFF) that
serves it live in the same container, on the same origin. It shows each user only what they are
entitled to and makes no access decision itself.

# Responsibilities

UI:

- Workflow launcher: list the workflows the user may start, for themselves or a team, and collect inputs.
- Run view: step-by-step progress of each node and its output when the node finishes, cancel and retry.
- Run history: the user's own runs, from every surface; team visibility is considered later.
- Inbox: human tasks (approvals, reviews, missing inputs) of the user's own runs.
- Artifacts: browse, preview and download what runs produced.
- Connections: let a user link and revoke their own accounts on downstream systems.
- Team context: choose which of the user's teams a run is for.

BFF:

- Sign the user in behind Identity-Aware Proxy and verify the signed IAP assertion (`x-goog-iap-jwt-assertion`: signature, issuer, audience) on every request. For now ([DEC-0010](../decisions/DEC-0010.md)) take the user's account ID and email from it, never from IAP's unsigned headers, and forward them as `X-SDLC-User-Id` and `X-SDLC-User-Email` to the agent runtime and user_agent_mcp, calling with the BFF's service account ID token. Never forward the assertion. The internal OAuth app of [DEC-0001](../decisions/DEC-0001.md) and [DEC-0009](../decisions/DEC-0009.md) is suspended until another surface needs user tokens.
- Forward the user's identity on every backend call; never call a backend with a service credential on the user's behalf.
- Shape backend APIs for the UI and relay the run event stream to the browser.
- Serve the UI's static assets, so the browser talks to one origin only.

# Out of scope

- Authorization: the [Access Policy](access-policy.md) decides, enforced by the services that own each resource.
- Administering configuration: that is declared in the [Configuration Registry](configuration-registry.md).

# Interfaces

- Provides: the web UI and the BFF API under one hostname.
- Consumes: the [Workflow Catalog](workflow-catalog.md) list, the run API and event stream of the [Workflow Engine](workflow-engine.md), task APIs of [Human Tasks](human-tasks.md), and the artifact and connection API of [user_agent_mcp](user-agent-mcp.md).

# Depends on

- [Identity](identity.md)
- [Workflow Catalog](workflow-catalog.md)
- [Workflow Engine](workflow-engine.md)
- [Human Tasks](human-tasks.md)
- [Artifact Store](artifact-store.md)
- [Connectors](connectors.md)
- [user_agent_mcp](user-agent-mcp.md)

# Owns

- User sessions. Nothing else durable beyond per-browser preferences.

# Requirements

- [FR-SURF-001: Custom UI](../requirements/functional/FR-SURF-001.md)
- [FR-SURF-004: Same behaviour on every surface](../requirements/functional/FR-SURF-004.md)
- [FR-IDN-001: Sign-in with Cloud Identity, federated from Entra ID](../requirements/functional/FR-IDN-001.md)
- [FR-TEAM-002: Team context](../requirements/functional/FR-TEAM-002.md)
- [FR-TEAM-003: Team runs visible to the team](../requirements/functional/FR-TEAM-003.md)
- [FR-TEAM-004: Many teams per user](../requirements/functional/FR-TEAM-004.md)
- [FR-WFL-003: Start a run](../requirements/functional/FR-WFL-003.md)
- [FR-WFL-008: Run events and history](../requirements/functional/FR-WFL-008.md)
- [FR-CONN-001: Per-user connections](../requirements/functional/FR-CONN-001.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-ARCH-001: sdlc_ui is one container](../requirements/non-functional/NFR-ARCH-001.md)
- [NFR-ARCH-002: Hostnames and service URLs are configuration](../requirements/non-functional/NFR-ARCH-002.md)
- [NFR-ARCH-003: Self-contained components](../requirements/non-functional/NFR-ARCH-003.md)
- [NFR-SEC-001: Authorization only in the platform's services](../requirements/non-functional/NFR-SEC-001.md)
- [NFR-SEC-003: Tokens stay server side](../requirements/non-functional/NFR-SEC-003.md)
- [NFR-SEC-007: sdlc_ui behind Identity-Aware Proxy](../requirements/non-functional/NFR-SEC-007.md)
- [NFR-REL-001: 99.5% availability](../requirements/non-functional/NFR-REL-001.md)
- [NFR-PERF-001: Application response under 5 seconds on average](../requirements/non-functional/NFR-PERF-001.md)
- [NFR-OPS-001: Reproducible images](../requirements/non-functional/NFR-OPS-001.md)
- [NFR-OPS-002: Local Docker Compose environment](../requirements/non-functional/NFR-OPS-002.md)
- [FR-WFL-009: Resume after signing in again](../requirements/functional/FR-WFL-009.md)
- [FR-AGT-005: Ad-hoc knowledge search and brainstorm chat](../requirements/functional/FR-AGT-005.md)

# Realisation

- One container image named `sdlc_ui`, holding both the UI build and the BFF.
- Deployed as one Cloud Run service in europe-west3, with Identity-Aware Proxy enabled on the service ([DEC-0001](../decisions/DEC-0001.md), accepted). Cloud Run service names allow only lowercase letters, digits
  and hyphens, so the service is `sdlc-ui`.
- Folder `sdlc_ui/`, self-contained; dependency URLs (user_agent_mcp, the ADK application) from environment variables; runs in the local Docker Compose environment.
- CopilotKit for the UI and BFF, with an AG-UI event stream from the agents.
- No admin view (effective-permission explorer) in the first release.
- Built (phase 3): the BFF verifies the IAP assertion on every request (locally, a fixed user), starts each
  chat as a runtime session for the verified user, streams answers through CopilotKit's runtime as AG-UI and
  replays a chat's history from the runtime for the same user; it stores nothing. Artifacts and connections
  pages use user_agent_mcp's HTTP API. Deployed as `sdlc-ui` with IAP on the service (`infra/gcp/sdlc_ui.tf`),
  IAP's service agent the only invoker.
- Built (phase 4a milestone 4): team chats and workflow questions.
  - "New chat" for one of the user's teams (checked against user_agent_mcp's `/api/me`) creates the runtime
    session with `sdlc_team` set, so the run starts in that team's scope; such chats are listed with their team
    and offer the workflows as suggestions ([FR-KNOW-004](../requirements/functional/FR-KNOW-004.md)).
  - Each workflow question (`adk_request_input`) is rendered in the chat with CopilotKit's human-in-the-loop
    hook: review findings with checkboxes (blockers and majors chosen) and a note, a team switch as yes or no,
    and the wait for a merge with a link to the pull request ([FR-HUM-001](../requirements/functional/FR-HUM-001.md),
    [FR-SDLC-004](../requirements/functional/FR-SDLC-004.md)). The BFF sends the answer to the runtime as the
    function response that resumes the workflow, and only for a question the same chat asked; a reopened chat
    shows its questions and answers, and an unanswered one can still be answered.
  - Only the root agent's messages are shown as chat: the drafts and reviewers' JSON of a workflow's own agents
    stay out of it.


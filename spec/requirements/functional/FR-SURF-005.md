---
type: Functional Requirement
title: "Third-party AI surfaces over A2A"
description: "Users reach the platform's workflows from other AI surfaces that speak A2A, such as Microsoft Copilot, through the A2A router and with their own identity."
tags: [requirement, surfaces]
status: draft
x-area: SURF
x-priority: must
x-implementation: parked
---

# Statement

The system shall let users reach its workflows from third-party AI surfaces that act as A2A clients, such
as Microsoft Copilot (through Copilot Studio), through the
[A2A router](FR-SURF-002.md), acting with the user's own identity.

# Acceptance criteria

- Each third-party surface is declared in configuration with a name and its own OAuth client. A token
  issued to an undeclared client is refused.
- The surface obtains the user's token by the OAuth 2.0 authorization-code flow against Google, so the
  user signs in with their Cloud Identity account (and so through Entra ID). No API key or other shared
  credential stands in for users.
- Copilot Studio can add the platform as a connected A2A agent with OAuth 2.0 in manual configuration
  (client ID, client secret, authorization, token and refresh URLs) once Copilot Studio's redirect URL is
  registered on that surface's OAuth client.
- A run started from a third-party surface records the surface's name, appears in the user's run history in
  sdlc_ui, and is subject to the same permissions as on any other surface.
- Revoking one surface's OAuth client stops that surface and no other.

# Notes

- Parked: Gemini Enterprise is the only AI surface for now; Microsoft Copilot and other third-party surfaces are enabled later.
- Coding harnesses use user_agent_mcp directly instead: [FR-SURF-006](FR-SURF-006.md).
- Copilot Studio cannot call a connected agent that requires user sign-in from a main agent that uses
  generic OAuth 2.0 token passthrough; such Copilot agents must use another authentication setup.
- Google does not support dynamic client registration for its OAuth clients, so Copilot Studio's
  *Dynamic* option does not apply; each surface gets a client created ahead of time.

# Citations

[1] [Connect to an agent over the Agent2Agent (A2A) protocol - Microsoft Copilot Studio](https://learn.microsoft.com/en-us/microsoft-copilot-studio/add-agent-agent-to-agent)
[2] [Add an A2A agent as a connected agent - Microsoft Copilot Studio](https://learn.microsoft.com/en-us/microsoft-copilot-studio/agents-experience/add-agent-to-agent)

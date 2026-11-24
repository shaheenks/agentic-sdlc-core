---
type: Non-Functional Requirement
title: "Local Docker Compose environment"
description: "All self-hosted components run locally with Docker Compose, each pointing at local or GCP services through environment-variable profiles."
tags: [requirement, operability]
status: draft
x-area: OPS
x-priority: must
x-implementation: planned
---

# Statement

The system shall provide a local Docker Compose environment that runs every self-hosted component for
development and testing, where each component can point at a local or a Google Cloud dependency through
environment-variable profiles.

# Acceptance criteria

- `docker compose up` starts sdlc_ui, user_agent_mcp, event_agent_mcp, the ADK application, knowledge search,
  knowledge ingest and the event gateway.
- Environment-variable profiles (for example `local` and `gcp-dev`) choose, per dependency, a local container or
  the development Google Cloud environment.
- Access to Google Cloud uses the developer's gcloud credentials (Application Default Credentials), mounted
  read-only; no service-account keys.
- The MCP servers' store mount is a git-ignored local folder in the `local` profile and the development artifact
  bucket through Cloud Storage FUSE in the `gcp-dev` profile ([NFR-SEC-004](NFR-SEC-004.md)); platform secrets
  come from the development project's Secret Manager.
- Gemini is reached through Vertex AI with the same gcloud credentials.
- The local environment is for development and testing only; it is not an environment of the platform.

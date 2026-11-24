---
type: Component
title: Connectors
description: Adapters to downstream SDLC systems - source control, issue trackers, wikis, CI - that read and write as the user with the user's own connection.
tags: [component, capability]
status: draft
x-layer: capability
x-depends-on: [/components/secrets, /components/configuration-registry]
x-satisfies: [/requirements/functional/FR-IDN-002, /requirements/functional/FR-CONN-001, /requirements/functional/FR-CONN-002, /requirements/functional/FR-CONN-003, /requirements/functional/FR-CONN-004, /requirements/functional/FR-CONN-005, /requirements/functional/FR-KNOW-001, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-SEC-005, /requirements/functional/FR-TRIG-003, /requirements/functional/FR-SDLC-012]
---

# Purpose

Workflows act on real systems: read a PR, create Jira stories, update a Confluence page. Connectors
do this as the user, so the downstream system's own permissions still apply.

# Responsibilities

- One adapter per provider and edition (for example GitHub, Bitbucket, Jira, Confluence, cloud and data-center editions).
- Manage per-user connections: OAuth or personal token, linked by the user, stored in [Secrets](secrets.md), revocable by the user.
- Manage system connections for the system identity (for example an app installation), scoped as configuration declares and used by unattended runs only, with credentials from environment variables.
- Restrict outbound calls to the hosts declared for each source.
- Normalise errors (not connected, expired, forbidden by the provider) so workflows can ask the user to reconnect.
- Serve both live tool calls and the [Ingest Pipeline](ingest-pipeline.md).

# Out of scope

- Whether the user may use a connector for a given resource: the [Access Policy](access-policy.md).

# Interfaces

- Provides: provider operations behind a uniform interface; connection management API.
- Consumes: source and host declarations; user credentials from [Secrets](secrets.md).

# Depends on

- [Secrets](secrets.md)
- [Configuration Registry](configuration-registry.md)

# Owns

- Connection records (who connected what, when, status); the credentials themselves are in Secrets.

# Requirements

- [FR-IDN-002: Act as the user end to end](../requirements/functional/FR-IDN-002.md)
- [FR-CONN-001: Per-user connections](../requirements/functional/FR-CONN-001.md)
- [FR-CONN-002: Reconnect instead of fail](../requirements/functional/FR-CONN-002.md)
- [FR-CONN-003: Downstream systems](../requirements/functional/FR-CONN-003.md)
- [FR-CONN-004: System connections](../requirements/functional/FR-CONN-004.md)
- [FR-CONN-005: Secrets never pass through agents](../requirements/functional/FR-CONN-005.md)
- [FR-KNOW-001: Ingest declared sources](../requirements/functional/FR-KNOW-001.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-SEC-005: Outbound host allowlist](../requirements/non-functional/NFR-SEC-005.md)
- [FR-TRIG-003: Results of unattended runs go back to the systems involved](../requirements/functional/FR-TRIG-003.md)
- [FR-SDLC-012: Jira tasks from findings](../requirements/functional/FR-SDLC-012.md)

# Realisation

- Required: GitHub, Bitbucket, Jira and Confluence, each in its cloud and Data Center editions (eight adapters
  behind one interface per kind of system). First phase: Jira, GitHub and Bitbucket in both editions;
  Confluence follows later.
- Every adapter supports user connections (user_agent, with the user's own token) and system connections (the
  event-based agents, with tokens from Secret Manager); the edition decides the sign-in (OAuth or API token in
  the cloud, personal access tokens in Data Center) and the webhook format the event gateway verifies.

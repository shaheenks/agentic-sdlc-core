---
type: Component
title: Access Policy
description: Resolves a user's effective permissions from declared roles and decides, deny by default, every request to list or use a workflow, tool, skill or data source.
tags: [component, control, security]
status: draft
x-layer: control
x-depends-on: [/components/directory, /components/configuration-registry, /components/audit-log]
x-satisfies: [/requirements/functional/FR-SURF-004, /requirements/functional/FR-IDN-004, /requirements/functional/FR-TEAM-002, /requirements/functional/FR-TEAM-003, /requirements/functional/FR-TEAM-004, /requirements/functional/FR-AUTHZ-001, /requirements/functional/FR-AUTHZ-002, /requirements/functional/FR-AUTHZ-003, /requirements/functional/FR-AUTHZ-004, /requirements/functional/FR-AUTHZ-005, /requirements/functional/FR-AUTHZ-006, /requirements/functional/FR-AUTHZ-007, /requirements/functional/FR-CFG-005, /requirements/functional/FR-WFL-003, /requirements/functional/FR-HUM-002, /requirements/functional/FR-SKILL-001, /requirements/functional/FR-ART-002, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-SEC-001, /requirements/non-functional/NFR-SEC-002, /requirements/non-functional/NFR-AUD-001, /requirements/functional/FR-KNOW-004]
---

# Purpose

The one place authorization is decided. Access is declared in configuration, never coded in agents or
prompts. The services that own each resource enforce the decision.

# Responsibilities

- Compute an effective policy per user and team context: the workflows they may start, the tools with their argument constraints, the skills, and the data sources with a classification ceiling for each.
- Decide each request (allow or deny) and name the rule that matched; deny when identity or config cannot be verified.
- Narrow the tools per surface to the tool groups declared for it.
- Apply rate limits and quotas per user and team.
- Send every decision to the [Audit Log](audit-log.md) with the configuration version.

# Out of scope

- Authentication: the [Identity](identity.md) component.
- Row filtering inside data stores, which apply the decision's data scope themselves.

# Interfaces

- Provides: `effective_policy(identity, team?)`, `authorize(identity, action, resource, args)`.
- Consumes: role, grant and limit declarations; memberships from the [Directory](directory.md).

# Depends on

- [Directory](directory.md)
- [Configuration Registry](configuration-registry.md)
- [Audit Log](audit-log.md)

# Owns

- An effective-policy cache keyed by identity, team and configuration version.

# Requirements

- [FR-SURF-004: Same behaviour on every surface](../requirements/functional/FR-SURF-004.md)
- [FR-IDN-004: System identity for unattended runs](../requirements/functional/FR-IDN-004.md)
- [FR-TEAM-002: Team context](../requirements/functional/FR-TEAM-002.md)
- [FR-TEAM-003: Team runs visible to the team](../requirements/functional/FR-TEAM-003.md)
- [FR-TEAM-004: Many teams per user](../requirements/functional/FR-TEAM-004.md)
- [FR-AUTHZ-001: Access declared in configuration](../requirements/functional/FR-AUTHZ-001.md)
- [FR-AUTHZ-002: Selective disclosure](../requirements/functional/FR-AUTHZ-002.md)
- [FR-AUTHZ-003: Authorize every call](../requirements/functional/FR-AUTHZ-003.md)
- [FR-AUTHZ-004: Data scope](../requirements/functional/FR-AUTHZ-004.md)
- [FR-AUTHZ-005: Rate limits and quotas](../requirements/functional/FR-AUTHZ-005.md)
- [FR-AUTHZ-006: Tool groups per surface](../requirements/functional/FR-AUTHZ-006.md)
- [FR-AUTHZ-007: Grants to teams and user groups](../requirements/functional/FR-AUTHZ-007.md)
- [FR-CFG-005: Configuration bucket](../requirements/functional/FR-CFG-005.md)
- [FR-WFL-003: Start a run](../requirements/functional/FR-WFL-003.md)
- [FR-HUM-002: Task routing](../requirements/functional/FR-HUM-002.md)
- [FR-SKILL-001: Skill packages](../requirements/functional/FR-SKILL-001.md)
- [FR-ART-002: Artifact ownership](../requirements/functional/FR-ART-002.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-SEC-001: Authorization only in the platform's services](../requirements/non-functional/NFR-SEC-001.md)
- [NFR-SEC-002: Deny by default, fail closed](../requirements/non-functional/NFR-SEC-002.md)
- [NFR-AUD-001: Audit every decision](../requirements/non-functional/NFR-AUD-001.md)
- [FR-KNOW-004: Knowledge scope: broad in chat, team in workflows](../requirements/functional/FR-KNOW-004.md)

# Realisation

- A library under `libs/`, embedded in user_agent_mcp and event_agent_mcp ([DEC-0005](../decisions/DEC-0005.md)).
- A shared library under `libs/`, self-contained, used by user_agent_mcp, Knowledge Search and the sdlc_ui BFF.
- A team run gets the intersection of the starter's own effective permissions and the team's grants, plus what everyone is granted; the starter's personal denies still apply ([FR-TEAM-002](../requirements/functional/FR-TEAM-002.md)).

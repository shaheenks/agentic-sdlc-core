---
type: Component
title: Audit Log
description: Append-only record of every authentication, authorization decision, run, human decision and configuration activation, without secrets or argument values.
tags: [component, records, security]
status: draft
x-layer: records
x-depends-on: []
x-satisfies: [/requirements/functional/FR-IDN-004, /requirements/functional/FR-CFG-003, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-PRIV-001, /requirements/non-functional/NFR-AUD-001, /requirements/non-functional/NFR-AUD-002, /requirements/non-functional/NFR-REL-002]
---

# Purpose

Answers "who did what, as whom, under which rule and configuration version" for any run or request.

# Responsibilities

- Accept structured audit events from every component with a common schema: actor, action, resource, decision, matched rule, configuration version, run and step IDs, request and trace IDs.
- Store them append-only.
- Never contain tokens, secrets, prompts or argument values.
- Support queries by user, team, run and time for auditors.

# Out of scope

- Operational metrics and traces: [Observability](observability.md).

# Interfaces

- Provides: `record(event)`, audit query API.
- Consumes: events from all components.

# Depends on

- None.

# Owns

- Audit events and their retention.

# Requirements

- [FR-IDN-004: System identity for unattended runs](../requirements/functional/FR-IDN-004.md)
- [FR-CFG-003: Activation per environment](../requirements/functional/FR-CFG-003.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-PRIV-001: No sensitive content in telemetry](../requirements/non-functional/NFR-PRIV-001.md)
- [NFR-AUD-001: Audit every decision](../requirements/non-functional/NFR-AUD-001.md)
- [NFR-AUD-002: Audit retention](../requirements/non-functional/NFR-AUD-002.md)
- [NFR-REL-002: Multi-zone production](../requirements/non-functional/NFR-REL-002.md)

# Realisation

- Structured JSON audit records with a unique tag (for example `log_type: sdlc_audit`), written by every
  service through standard logging to the project's standard (`_Default`) Cloud Logging bucket; 30-day
  retention, no lock, no dedicated bucket.

# Open questions

- Who may read the audit records beyond the standard log-viewer roles is considered later.

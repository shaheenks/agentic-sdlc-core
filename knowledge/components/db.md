---
type: Component
title: db
description: Database bootstrap and the numbered, append-only migrations that define the schema and its row-level security.
area: Data
tags:
- component
- data
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../db
satisfies:
- /requirements/functional/FR-ART-001
- /requirements/functional/FR-ART-002
- /requirements/functional/FR-AUTHZ-005
- /requirements/functional/FR-AUTHZ-006
- /requirements/functional/FR-KNOW-002
- /requirements/functional/FR-KNOW-003
- /requirements/non-functional/NFR-REL-004
- /requirements/non-functional/NFR-SEC-005
- /requirements/non-functional/NFR-SEC-010
verified_by:
- tests/db
---

# Purpose

Defines schema `sdlc`: sources, documents, chunks, graph tables and artifacts, each with RLS enabled and forced, and the three database roles.

Code: `db`

# Responsibilities

- `db/bootstrap`: extension, roles, schema, grants.
- `db/migrations` 001 to 007: knowledge, graph, media type, item metadata, artifacts, artifact versions, full-text search.

# Depends on

No other component.

# Requirements

- [FR-ART-001: Save and manage artifacts](../requirements/functional/FR-ART-001.md) - Artifact table under owner RLS.
- [FR-ART-002: Artifact versions](../requirements/functional/FR-ART-002.md) - Artifact version rows.
- [FR-AUTHZ-005: Data access granted per source](../requirements/functional/FR-AUTHZ-005.md) - RLS policies on source and classification.
- [FR-AUTHZ-006: Team roles are scoped to their team](../requirements/functional/FR-AUTHZ-006.md) - Migration 008: every row is compared with the ceiling of its own source.
- [FR-KNOW-002: Knowledge search with citations](../requirements/functional/FR-KNOW-002.md) - Chunk table with vector and full-text indexes.
- [FR-KNOW-003: Knowledge graph queries](../requirements/functional/FR-KNOW-003.md) - Entity, mention and edge tables.
- [NFR-REL-004: Repeatable data changes](../requirements/non-functional/NFR-REL-004.md) - Append-only numbered migrations.
- [NFR-SEC-005: Row-level security on all data](../requirements/non-functional/NFR-SEC-005.md) - RLS enabled and forced on every data table.
- [NFR-SEC-010: Least-privilege runtime](../requirements/non-functional/NFR-SEC-010.md) - Separate owner, app and ingest roles.

# Verification

- `tests/db`

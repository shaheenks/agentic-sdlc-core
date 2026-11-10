---
type: Component
title: sdlc_db
description: 'Postgres and pgvector access under row-level security: knowledge search, graph, artifact metadata, bootstrap and migrations.'
area: Libraries
tags:
- component
- libraries
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../libs/sdlc_db
satisfies:
- /requirements/functional/FR-ART-001
- /requirements/functional/FR-ART-002
- /requirements/functional/FR-AUTHZ-005
- /requirements/functional/FR-KNOW-001
- /requirements/functional/FR-KNOW-002
- /requirements/functional/FR-KNOW-003
- /requirements/non-functional/NFR-PRIV-002
- /requirements/non-functional/NFR-QUAL-001
- /requirements/non-functional/NFR-REL-004
- /requirements/non-functional/NFR-SEC-005
- /requirements/non-functional/NFR-SEC-010
verified_by:
- tests/db
- tests/e2e/test_db.py
- tests/evals/test_retrieval_eval.py
sources:
- id: readme
  resource: ../../libs/sdlc_db/README.md
  title: libs/sdlc_db/README.md
---

# Purpose

The only way code reads or writes the database. Reads run inside `scoped()` or `owner_scoped()`, which set the row-level-security context for one transaction.

Code: `libs/sdlc_db`

# Responsibilities

- `scoped()`: allowed sources and classification ceiling from the caller's policy.
- Knowledge queries: vector, keyword, rank fusion; ingest writes.
- Graph writes and RLS-scoped traversal.
- Artifact metadata under owner RLS.
- Embedders (Gemini; hash embedder for tests).
- `sdlc-db bootstrap` and `migrate`; connection strings per role.

# Depends on

- [sdlc_config](sdlc_config.md)

# Requirements

- [FR-ART-001: Save and manage artifacts](../requirements/functional/FR-ART-001.md) - Artifact metadata under owner RLS.
- [FR-ART-002: Artifact versions](../requirements/functional/FR-ART-002.md) - Immutable version rows and the latest-version check.
- [FR-AUTHZ-005: Data access granted per source](../requirements/functional/FR-AUTHZ-005.md) - Sets the RLS context that limits rows to readable sources.
- [FR-KNOW-001: Ingest declared sources](../requirements/functional/FR-KNOW-001.md) - Writes documents, chunks and embeddings for ingest.
- [FR-KNOW-002: Knowledge search with citations](../requirements/functional/FR-KNOW-002.md) - Vector and keyword search with rank fusion.
- [FR-KNOW-003: Knowledge graph queries](../requirements/functional/FR-KNOW-003.md) - Stores the graph per source and walks it at query time.
- [NFR-PRIV-002: Hidden resources are not disclosed](../requirements/non-functional/NFR-PRIV-002.md) - Another owner's artifact rows are invisible.
- [NFR-QUAL-001: Retrieval quality gate](../requirements/non-functional/NFR-QUAL-001.md) - Retrieval is what the retrieval eval measures.
- [NFR-REL-004: Repeatable data changes](../requirements/non-functional/NFR-REL-004.md) - Checksummed migrations and idempotent bootstrap.
- [NFR-SEC-005: Row-level security on all data](../requirements/non-functional/NFR-SEC-005.md) - All reads go through the scoped context; bootstrap refuses roles that bypass RLS.
- [NFR-SEC-010: Least-privilege runtime](../requirements/non-functional/NFR-SEC-010.md) - One connection identity per database role.

# Verification

- `tests/db`
- `tests/e2e/test_db.py`
- `tests/evals/test_retrieval_eval.py`

---
type: Component
title: ingest_loaders
description: 'One loader per source type: local folder, git, GCS, Confluence and Jira.'
area: Pipelines
tags:
- component
- pipelines
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../ingest/loaders
satisfies:
- /requirements/functional/FR-KNOW-001
- /requirements/functional/FR-KNOW-004
- /requirements/non-functional/NFR-SEC-008
verified_by:
- tests/ingest/test_loaders.py
- tests/ingest/test_git_source.py
- tests/ingest/test_remote_git.py
- tests/ingest/test_gcs.py
- tests/ingest/test_confluence.py
- tests/ingest/test_jira.py
sources:
- id: readme
  resource: ../../ingest/loaders/README.md
  title: ingest/loaders/README.md
---

# Purpose

Each loader reads one source and yields items for the pipeline; the pipeline never talks to a source system itself.

Code: `ingest/loaders`

# Responsibilities

- Loader registry: source type to factory.
- `local_folder`, `git` (pinned SHA or tracked branch; GitHub and Bitbucket remotes), `gcs`, `confluence`, `jira`.
- Skips items that are restricted in the source system.

# Depends on

- [sdlc_connectors](sdlc_connectors.md)
- [sdlc_config](sdlc_config.md)
- [sdlc_secrets](sdlc_secrets.md)

# Requirements

- [FR-KNOW-001: Ingest declared sources](../requirements/functional/FR-KNOW-001.md) - Reads every supported source type and leaves out natively restricted items.
- [FR-KNOW-004: PDF ingestion](../requirements/functional/FR-KNOW-004.md) - Yields PDF files alongside text files.
- [NFR-SEC-008: Controlled egress](../requirements/non-functional/NFR-SEC-008.md) - Remote sources are reached only through the allowlisted HTTP client.

# Verification

- `tests/ingest/test_loaders.py`
- `tests/ingest/test_git_source.py`
- `tests/ingest/test_remote_git.py`
- `tests/ingest/test_gcs.py`
- `tests/ingest/test_confluence.py`
- `tests/ingest/test_jira.py`

---
type: Component
title: sdlc_artifacts
description: Artifact content store (local folder or GCS) and the limits on what an artifact may be.
area: Libraries
tags:
- component
- libraries
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../libs/sdlc_artifacts
satisfies:
- /requirements/functional/FR-ART-001
- /requirements/non-functional/NFR-SEC-011
verified_by:
- tests/artifacts
sources:
- id: readme
  resource: ../../libs/sdlc_artifacts/README.md
  title: libs/sdlc_artifacts/README.md
---

# Purpose

Stores artifact bytes under `artifacts/<owner oid>/<artifact id>`. Used only by the MCP server; ownership and metadata live in Postgres.

Code: `libs/sdlc_artifacts`

# Responsibilities

- Content stores selected by `SDLC_ARTIFACT_STORE` (`file://` or `gs://`).
- Limits: text only, size, count per user, file-name rules.

# Depends on

No other component.

# Requirements

- [FR-ART-001: Save and manage artifacts](../requirements/functional/FR-ART-001.md) - Stores content and enforces the artifact limits.
- [NFR-SEC-011: Browser-facing hardening](../requirements/non-functional/NFR-SEC-011.md) - Restricts artifacts to text media types served as attachments.

# Verification

- `tests/artifacts`

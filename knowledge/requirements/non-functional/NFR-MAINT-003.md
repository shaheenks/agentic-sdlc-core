---
type: Non-Functional Requirement
title: CI runs without secrets
description: The full CI suite runs with no secrets and no cloud calls.
area: Maintainability
tags:
- requirement
- non-functional
- maintainability
status: draft
priority: must
implementation: live
sources:
- id: change
  resource: ../../changes/CH-0010.md
  title: CH-0010 Continuous deployment to GCP dev
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

The checks and tests in continuous integration shall run without secrets or calls to cloud services. Only the deployment workflow reaches the cloud.

# Acceptance criteria

- Tests pass without `.env`, using placeholder Entra IDs and OAuth client IDs, example tenant files, a hash embedder, fake Entra and Google tokens and a fake Groups API.
- The `ci` workflow covers lint, config validation, the permission diff, UI checks, database tests and Terraform checks, and holds no secret and no cloud credential.
- The deploy workflow (NFR-OPS-002) is a separate workflow. It runs only on `main`, after `ci` passes, and gets its GCP access through Workload Identity Federation, never a stored key.

# Notes

Modified by CH-0010.

Modified by [CH-0021](../../changes/CH-0021.md): per stack (Entra / GCP), design N7 to N10 and N13.

---
type: Non-Functional Requirement
title: "Hosted on Google Cloud"
description: "Every platform component runs on Google Cloud."
tags: [requirement, hosting]
status: draft
x-area: HOST
x-priority: must
x-implementation: planned
---

# Statement

The system shall host all of its components on Google Cloud.

# Acceptance criteria

- Every component concept names the Google Cloud service it runs on under `# Realisation`.
- Nothing the platform runs is hosted outside Google Cloud; only the identity provider and downstream systems may be external.

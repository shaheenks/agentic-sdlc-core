---
type: Non-Functional Requirement
title: "Managed services first"
description: "Components run on managed or serverless Google Cloud services."
tags: [requirement, hosting]
status: draft
x-area: HOST
x-priority: should
x-implementation: planned
---

# Statement

The system shall run components on managed or serverless Google Cloud services in preference to self-managed virtual machines or clusters.

# Acceptance criteria

- Each component's `# Realisation` names a managed service, or records why one does not fit.
